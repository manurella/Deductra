"""CR-005 acceptance tests for deterministic verified human reasoning."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from deductra.domain.atoms import AssignmentAtom, Atom
from deductra.domain.constraints import AllDifferentConstraint
from deductra.domain.puzzle import DisplaySpec, ProvenanceBundle, PuzzleIdentity, PuzzleSpec
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.reasoning import (
    HumanReasoningEngine,
    HumanSolveContext,
    HumanSolveStatus,
    ProducerRef,
    ProposedDeduction,
    RuleApplicationCandidate,
    RuleReference,
    ValueAssigned,
    create_initial_state,
)
from deductra.reasoning.schema import rendered_human_solve_trace_json_schema
from deductra.reasoning.state import PuzzleState, build_state
from deductra.verification import (
    CpSatProofBackend,
    CrossVerificationCoordinator,
    VerifiedRuleAuthority,
    Z3ProofBackend,
)

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]
X = "deductra:variable:x"
Y = "deductra:variable:y"
A = "deductra:value:a"
B = "deductra:value:b"


def puzzle() -> PuzzleSpec:
    values = (DomainValue(value_id=A, label="A"), DomainValue(value_id=B, label="B"))
    return PuzzleSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:human-engine-test",
            revision_id="deductra:revision:human-engine-test:1",
            family_id="human-engine-test",
            schema_version="1.0.0",
            title="Human engine test",
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
                variable_id=item,
                label=item.rsplit(":", 1)[1].upper(),
                domain_id="deductra:domain:letters",
                role="answer",
            )
            for item in (X, Y)
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


def state() -> PuzzleState:
    return build_state(
        state_id="deductra:state:human-source",
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


def context() -> HumanSolveContext:
    return HumanSolveContext(
        trace_id="deductra:trace:human-engine",
        correlation_id="deductra:correlation:human-engine",
        producer=ProducerRef(
            producer_id="deductra:producer:human-engine-test",
            kind="rule_engine",
            version="1.0.0",
        ),
        occurred_at=NOW,
        previous_event_hash="a" * 64,
    )


class AssignmentRule:
    def __init__(self, *, suffix: str, value_id: str, rank: int) -> None:
        self.reference = RuleReference(
            rule_id=f"deductra:rule:{suffix}",
            rule_version="1.0.0",
            family_scope=("human-engine-test",),
            title=f"Assign {value_id}",
            technique_rank=rank,
        )
        self._value_id = value_id

    def find_applications(
        self, puzzle: PuzzleSpec, state: PuzzleState
    ) -> tuple[RuleApplicationCandidate, ...]:
        del puzzle
        if len(state.candidate_domains[X]) == 1:
            return ()
        return (
            RuleApplicationCandidate(
                candidate_id=f"deductra:candidate:{self.reference.rule_id.rsplit(':', 1)[1]}",
                rule=self.reference,
                source_state_hash=state.state_hash,
                premises=(AssignmentAtom(variable_id=Y, value_id=A),),
                affected_variables=(X,),
                supporting_constraints=("deductra:constraint:different",),
                information_gain=1,
                pedagogical_cost=self.reference.technique_rank,
                tie_break_key=self.reference.rule_id,
            ),
        )

    def apply(self, candidate: RuleApplicationCandidate, state: PuzzleState) -> ProposedDeduction:
        del state
        return ProposedDeduction(
            candidate_id=candidate.candidate_id,
            source_state_hash=candidate.source_state_hash,
            rule=self.reference,
            premises=candidate.premises,
            conclusions=(AssignmentAtom(variable_id=X, value_id=self._value_id),),
            affected_variables=candidate.affected_variables,
            supporting_constraints=candidate.supporting_constraints,
            explanation_parameters={"selected_value": self._value_id},
        )


def engine(*rules: AssignmentRule) -> HumanReasoningEngine:
    return HumanReasoningEngine(
        rules,
        VerifiedRuleAuthority(
            CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
        ),
    )


def test_valid_rule_is_verified_and_solves_without_hidden_search() -> None:
    trace = engine(AssignmentRule(suffix="valid", value_id=B, rank=1)).solve(
        puzzle(), state(), context()
    )
    assert trace.status is HumanSolveStatus.SOLVED
    assert len(trace.events) == 1
    payload = trace.events[0].payload
    assert isinstance(payload, ValueAssigned)
    assert payload.origin == "human_rule"
    assert trace.attempts[0].verification_status.value == "cross_verified"


def test_invalid_deduction_is_rejected_and_state_is_unchanged() -> None:
    initial = state()
    trace = engine(AssignmentRule(suffix="invalid", value_id=A, rank=1)).solve(
        puzzle(), initial, context()
    )
    assert trace.status is HumanSolveStatus.STALLED
    assert trace.stalled_reason == "HUMAN_RULES_EXHAUSTED"
    assert trace.final_state_hash == initial.state_hash
    assert trace.events == ()
    assert trace.attempts[0].verification_status.value == "rejected"


def test_rule_order_does_not_change_canonical_trace() -> None:
    invalid = AssignmentRule(suffix="invalid", value_id=A, rank=0)
    valid = AssignmentRule(suffix="valid", value_id=B, rank=1)
    first = engine(valid, invalid).solve(puzzle(), state(), context())
    second = engine(invalid, valid).solve(puzzle(), state(), context())
    assert first.model_dump_json() == second.model_dump_json()


def test_no_rules_stalls_without_search_fallback() -> None:
    trace = HumanReasoningEngine(
        (), VerifiedRuleAuthority(CrossVerificationCoordinator((Z3ProofBackend(),)))
    ).solve(puzzle(), state(), context())
    assert trace.status is HumanSolveStatus.STALLED
    assert trace.attempts == ()
    assert trace.events == ()


def test_already_solved_state_finishes_without_discovery() -> None:
    solved = create_initial_state(
        puzzle().model_copy(
            update={
                "givens": (
                    AssignmentAtom(variable_id=X, value_id=B),
                    AssignmentAtom(variable_id=Y, value_id=A),
                )
            }
        ),
        state_id="deductra:state:solved",
        branch_id="deductra:branch:root",
        sequence_no=1,
    )
    trace = HumanReasoningEngine(
        (), VerifiedRuleAuthority(CrossVerificationCoordinator((Z3ProofBackend(),)))
    ).solve(puzzle(), solved, context())
    assert trace.status is HumanSolveStatus.SOLVED


def test_checked_in_human_trace_schema_is_current() -> None:
    path = ROOT / "schemas" / "human-solve-trace-v1.schema.json"
    assert path.read_text(encoding="utf-8") == rendered_human_solve_trace_json_schema()
