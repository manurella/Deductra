"""CR-004 acceptance tests for independent proof verification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint
from deductra.domain.puzzle import DisplaySpec, ProvenanceBundle, PuzzleIdentity, PuzzleSpec
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.reasoning.events import EventEnvelope, ProducerRef, ValueAssigned
from deductra.reasoning.integrity import seal_event
from deductra.reasoning.state import PuzzleState, build_state
from deductra.verification import (
    AssignmentNegation,
    CpSatProofBackend,
    CrossVerificationCoordinator,
    EliminationNegation,
    ProofObligation,
    VerificationRejectedError,
    VerificationStatus,
    Z3ProofBackend,
    apply_verified_event,
)
from deductra.verification.contracts import (
    BackendResult,
    VerificationCertificate,
    build_certificate,
)
from deductra.verification.schema import rendered_verification_record_json_schema

NOW = datetime(2026, 7, 16, tzinfo=UTC)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
X = "deductra:variable:x"
Y = "deductra:variable:y"
A = "deductra:value:a"
B = "deductra:value:b"


def puzzle() -> PuzzleSpec:
    values = (
        DomainValue(value_id=A, label="A"),
        DomainValue(value_id=B, label="B"),
    )
    return PuzzleSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:verification-test",
            revision_id="deductra:revision:verification-test:1",
            family_id="verification-test",
            schema_version="1.0.0",
            title="Verification test",
            source_kind="golden",
            created_at=NOW,
        ),
        domains=(
            Domain(
                domain_id="deductra:domain:letters",
                values=values,
                ordered=False,
                distinct_by_default=True,
            ),
        ),
        variables=tuple(
            Variable(
                variable_id=variable_id,
                label=variable_id.rsplit(":", 1)[1].upper(),
                domain_id="deductra:domain:letters",
                role="answer",
            )
            for variable_id in (X, Y)
        ),
        constraints=(
            AllDifferentConstraint(
                constraint_id="deductra:constraint:different",
                label="Values differ",
                variable_ids=(X, Y),
            ),
        ),
        clues=(),
        givens=(),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def source_state():
    return build_state(
        state_id="deductra:state:verification-source",
        puzzle_revision_id=puzzle().identity.revision_id,
        sequence_no=1,
        branch_id="deductra:branch:root",
        candidate_domains={X: frozenset({A, B}), Y: frozenset({A})},
        asserted_atoms=cast(
            frozenset[Atom],
            frozenset({cast(Any, AssignmentAtom(variable_id=Y, value_id=A))}),
        ),
        rejected_atoms=frozenset(),
        active_constraint_ids=frozenset({"deductra:constraint:different"}),
        contradiction_ids=(),
    )


def assignment_obligation(value_id: str = B) -> ProofObligation:
    state = source_state()
    return ProofObligation(
        obligation_id=f"deductra:obligation:assign-{value_id.rsplit(':', 1)[1]}",
        puzzle_revision_id=state.puzzle_revision_id,
        source_state_hash=state.state_hash,
        claimed_conclusions=(AssignmentAtom(variable_id=X, value_id=value_id),),
        negated_claim=AssignmentNegation(variable_id=X, value_id=value_id),
    )


def elimination_obligation() -> ProofObligation:
    state = source_state()
    return ProofObligation(
        obligation_id="deductra:obligation:eliminate-a",
        puzzle_revision_id=state.puzzle_revision_id,
        source_state_hash=state.state_hash,
        claimed_conclusions=(ExclusionAtom(variable_id=X, value_id=A),),
        negated_claim=EliminationNegation(variable_id=X, value_id=A),
    )


@pytest.mark.parametrize("obligation", [assignment_obligation(), elimination_obligation()])
def test_independent_backends_cross_verify_unsatisfiable_negations(
    obligation: ProofObligation,
) -> None:
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        puzzle(), source_state(), obligation
    )

    assert decision.status is VerificationStatus.CROSS_VERIFIED
    assert {item.result for item in decision.certificates} == {"unsat"}
    assert {item.backend_id for item in decision.certificates} == {"z3", "cp-sat"}


def test_satisfiable_negation_rejects_deduction_and_preserves_state() -> None:
    obligation = assignment_obligation(A)
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        puzzle(), source_state(), obligation
    )
    assert decision.status is VerificationStatus.REJECTED
    assert {item.result for item in decision.certificates} == {"sat"}

    with pytest.raises(VerificationRejectedError):
        apply_verified_event(source_state(), assignment_event(obligation), obligation, decision)
    assert source_state().candidate_domains[X] == frozenset({A, B})


def assignment_event(obligation: ProofObligation) -> EventEnvelope:
    conclusion = obligation.claimed_conclusions[0]
    if not isinstance(conclusion, AssignmentAtom):
        raise ValueError("assignment_event requires an assignment conclusion")
    return seal_event(
        event_id="deductra:event:verification:2",
        trace_id="deductra:trace:verification",
        puzzle_revision_id=obligation.puzzle_revision_id,
        branch_id="deductra:branch:root",
        sequence_no=2,
        schema_version="1.0.0",
        occurred_at=NOW,
        producer=ProducerRef(
            producer_id="deductra:producer:verification-test",
            kind="system",
            version="1.0.0",
        ),
        correlation_id="deductra:correlation:verification",
        previous_event_hash="a" * 64,
        payload=ValueAssigned(
            variable_id=X,
            value_id=conclusion.value_id,
            source_state_hash=obligation.source_state_hash,
            result_state_id="deductra:state:verification-result",
            origin="human_rule",
        ),
    )


def test_cross_verified_assignment_alone_authorizes_reduction() -> None:
    obligation = assignment_obligation()
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        puzzle(), source_state(), obligation
    )
    result = apply_verified_event(
        source_state(), assignment_event(obligation), obligation, decision
    )
    assert result.candidate_domains[X] == frozenset({B})


class FixedBackend:
    encoding_version = "finite-domain-v1"

    def __init__(self, backend_id: str, result: BackendResult) -> None:
        self.backend_id = backend_id
        self.backend_version = "test"
        self._result: BackendResult = result

    def verify(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
        obligation: ProofObligation,
        *,
        timeout_ms: int,
    ) -> VerificationCertificate:
        del puzzle, state, timeout_ms
        return build_certificate(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            encoding_version=self.encoding_version,
            obligation_id=obligation.obligation_id,
            result=self._result,
            duration_ms=1,
            raw_artifact_hash="b" * 64,
        )


def test_unknown_is_inconclusive_and_disagreement_is_quarantined() -> None:
    obligation = assignment_obligation()
    unknown = CrossVerificationCoordinator((FixedBackend("one", "unknown"),)).verify(
        puzzle(), source_state(), obligation
    )
    disagreement = CrossVerificationCoordinator(
        (FixedBackend("one", "sat"), FixedBackend("two", "unsat"))
    ).verify(puzzle(), source_state(), obligation)
    assert unknown.status is VerificationStatus.INCONCLUSIVE
    assert disagreement.status is VerificationStatus.QUARANTINED
    assert not unknown.accepted and not disagreement.accepted


def test_certificate_integrity_and_checked_in_schema() -> None:
    certificate = Z3ProofBackend().verify(
        puzzle(), source_state(), assignment_obligation(), timeout_ms=5_000
    )
    payload = certificate.model_dump()
    payload["duration_ms"] += 1
    with pytest.raises(ValidationError, match="certificate_hash"):
        VerificationCertificate.model_validate(payload)

    schema = REPOSITORY_ROOT / "schemas" / "verification-record-v1.schema.json"
    assert schema.read_text(encoding="utf-8") == rendered_verification_record_json_schema()
