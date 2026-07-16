"""Verification adapter implementing the human reasoning authority port."""

from __future__ import annotations

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.engine import (
    DeductionAuthorityResult,
    DeductionAuthorityStatus,
)
from deductra.reasoning.events import EventEnvelope
from deductra.reasoning.rules import ProposedDeduction
from deductra.reasoning.state import PuzzleState
from deductra.verification.contracts import (
    AssignmentNegation,
    EliminationNegation,
    ProofObligation,
)
from deductra.verification.coordinator import CrossVerificationCoordinator, apply_verified_event


class VerifiedRuleAuthority:
    """Prove proposed human deductions and apply only accepted events."""

    def __init__(self, coordinator: CrossVerificationCoordinator) -> None:
        self._coordinator = coordinator

    def evaluate(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
        proposal: ProposedDeduction,
        event: EventEnvelope,
        *,
        timeout_ms: int,
    ) -> DeductionAuthorityResult:
        """Bridge a human proposal through CR-004 verification and reduction."""
        conclusion = proposal.conclusions[0]
        if not isinstance(conclusion, (AssignmentAtom, ExclusionAtom)):
            raise ValueError("verified rule authority supports assignment and exclusion only")
        digest = canonical_sha256(
            {
                "candidate_id": proposal.candidate_id,
                "proposal": proposal,
                "source_state_hash": proposal.source_state_hash,
            }
        )
        negated = (
            AssignmentNegation(variable_id=conclusion.variable_id, value_id=conclusion.value_id)
            if isinstance(conclusion, AssignmentAtom)
            else EliminationNegation(
                variable_id=conclusion.variable_id, value_id=conclusion.value_id
            )
        )
        obligation = ProofObligation(
            obligation_id=f"deductra:obligation:{digest}",
            puzzle_revision_id=puzzle.identity.revision_id,
            source_state_hash=proposal.source_state_hash,
            assumptions=proposal.premises,
            claimed_conclusions=(conclusion,),
            negated_claim=negated,
        )
        decision = self._coordinator.verify(puzzle, state, obligation, timeout_ms=timeout_ms)
        result_state = (
            apply_verified_event(state, event, obligation, decision) if decision.accepted else None
        )
        return DeductionAuthorityResult(
            status=DeductionAuthorityStatus(decision.status.value),
            obligation_id=obligation.obligation_id,
            certificate_ids=tuple(sorted(item.certificate_id for item in decision.certificates)),
            reason=decision.reason,
            result_state=result_state,
        )
