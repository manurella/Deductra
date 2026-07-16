"""Cross-backend decisions and the verified reducer authorization boundary."""

from __future__ import annotations

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.puzzle import PuzzleSpec
from deductra.reasoning.events import CandidatesEliminated, EventEnvelope, ValueAssigned
from deductra.reasoning.reducer import reduce_state
from deductra.reasoning.state import PuzzleState
from deductra.verification.contracts import (
    ProofObligation,
    VerificationBackend,
    VerificationDecision,
    VerificationStatus,
)


class VerificationRejectedError(ValueError):
    """A verification decision does not authorize canonical state reduction."""


class CrossVerificationCoordinator:
    """Run independent backends and classify agreement without weakening unknowns."""

    def __init__(self, backends: tuple[VerificationBackend, ...]) -> None:
        if not backends:
            raise ValueError("at least one verification backend is required")
        if len({item.backend_id for item in backends}) != len(backends):
            raise ValueError("verification backend identifiers must be unique")
        self._backends = backends

    def verify(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
        obligation: ProofObligation,
        *,
        timeout_ms: int = 5_000,
    ) -> VerificationDecision:
        """Return verified, rejected, inconclusive, or quarantined authority."""
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        certificates = tuple(
            backend.verify(puzzle, state, obligation, timeout_ms=timeout_ms)
            for backend in self._backends
        )
        results = {item.result for item in certificates}
        if {"sat", "unsat"} <= results:
            status = VerificationStatus.QUARANTINED
            reason = "independent backends disagree on satisfiability"
        elif "invalid" in results:
            status = VerificationStatus.REJECTED
            reason = "at least one backend rejected the encoding"
        elif "unknown" in results:
            status = VerificationStatus.INCONCLUSIVE
            reason = "at least one backend returned unknown or timed out"
        elif results == {"unsat"}:
            status = (
                VerificationStatus.BACKEND_VERIFIED
                if len(certificates) == 1
                else VerificationStatus.CROSS_VERIFIED
            )
            reason = "the negated claim is unsatisfiable"
        else:
            status = VerificationStatus.REJECTED
            reason = "the negated claim is satisfiable"
        return VerificationDecision(
            obligation_id=obligation.obligation_id,
            status=status,
            certificates=certificates,
            reason=reason,
        )


def apply_verified_event(
    previous: PuzzleState,
    event: EventEnvelope,
    obligation: ProofObligation,
    decision: VerificationDecision,
) -> PuzzleState:
    """Apply only an event exactly supported by an accepted proof decision."""
    if not decision.accepted:
        raise VerificationRejectedError("verification decision does not authorize reduction")
    if decision.obligation_id != obligation.obligation_id:
        raise VerificationRejectedError("decision and obligation identifiers do not match")
    if obligation.source_state_hash != previous.state_hash:
        raise VerificationRejectedError("obligation source state is stale")
    if len(obligation.claimed_conclusions) != 1:
        raise VerificationRejectedError("verified reduction requires one conclusion")

    conclusion = obligation.claimed_conclusions[0]
    payload = event.payload
    if isinstance(payload, ValueAssigned):
        expected = AssignmentAtom(variable_id=payload.variable_id, value_id=payload.value_id)
    elif isinstance(payload, CandidatesEliminated) and len(payload.value_ids) == 1:
        expected = ExclusionAtom(
            variable_id=payload.variable_id,
            value_id=payload.value_ids[0],
        )
    else:
        raise VerificationRejectedError("event is outside the CR-004 verified reducer boundary")
    if conclusion != expected:
        raise VerificationRejectedError("event conclusion does not match the proof obligation")
    return reduce_state(previous, event)
