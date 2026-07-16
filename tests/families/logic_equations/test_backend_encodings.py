"""Differential acceptance tests for FAM-LE-003 backend encodings."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import (
    AllDifferentConstraint,
    ArithmeticConstraint,
    OrderConstraint,
)
from deductra.domain.expressions import (
    Add,
    And,
    BooleanExpression,
    Constant,
    Equal,
    ExactDivide,
    GreaterThan,
    Implies,
    LessThan,
    Modulo,
    Multiply,
    NotEqual,
    Or,
    VariableReference,
)
from deductra.domain.puzzle import (
    Clue,
    DisplaySpec,
    ProvenanceBundle,
    PuzzleIdentity,
    PuzzleSpec,
)
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_equations import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicEquationsSpec,
    logic_equations_rules,
)
from deductra.reasoning import (
    HumanReasoningEngine,
    HumanSolveContext,
    HumanSolveStatus,
    ProducerRef,
)
from deductra.reasoning.state import PuzzleState, create_initial_state
from deductra.verification import (
    AssignmentNegation,
    CpSatProofBackend,
    CrossVerificationCoordinator,
    EliminationNegation,
    ProofObligation,
    VerificationStatus,
    VerifiedRuleAuthority,
    Z3ProofBackend,
)

NOW = datetime(2026, 7, 16, 15, 0, tzinfo=UTC)
DOMAIN = "deductra:domain:logic-equations-backend-test"
A = "deductra:variable:a"
B = "deductra:variable:b"
C = "deductra:variable:c"
V1 = "deductra:value:1"
V2 = "deductra:value:2"
V3 = "deductra:value:3"
ARITHMETIC = "deductra:constraint:arithmetic"


def variable(variable_id: str) -> VariableReference:
    return VariableReference(variable_id=variable_id)


def constant(value: int) -> Constant:
    return Constant(value=value)


def puzzle(
    expression: BooleanExpression,
    *,
    givens: tuple[AssignmentAtom, ...] = (),
) -> LogicEquationsSpec:
    return LogicEquationsSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:logic-equations-backend-test",
            revision_id="deductra:revision:logic-equations-backend-test:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title="Backend encoding fixture",
            source_kind="user",
            created_at=NOW,
        ),
        domains=(
            Domain(
                domain_id=DOMAIN,
                values=tuple(
                    DomainValue(
                        value_id=f"deductra:value:{value}",
                        label=str(value),
                        ordinal=value,
                        numeric_value=value,
                    )
                    for value in range(1, 4)
                ),
                ordered=True,
                distinct_by_default=True,
            ),
        ),
        variables=tuple(
            Variable(
                variable_id=variable_id,
                label=variable_id.rsplit(":", 1)[1].upper(),
                domain_id=DOMAIN,
                role="arithmetic",
            )
            for variable_id in (A, B, C)
        ),
        constraints=(
            AllDifferentConstraint(
                constraint_id="deductra:constraint:all-different",
                label="All values differ",
                variable_ids=(A, B, C),
            ),
            ArithmeticConstraint(
                constraint_id=ARITHMETIC,
                label="Arithmetic clue",
                source_clue_id="deductra:clue:arithmetic",
                expression=expression,
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:arithmetic",
                text="A normalized arithmetic clue.",
                constraint_ids=(ARITHMETIC,),
                locale="en",
            ),
        ),
        givens=givens,
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def state(specification: PuzzleSpec) -> PuzzleState:
    return create_initial_state(
        specification,
        state_id="deductra:state:logic-equations-backend-test",
        branch_id="deductra:branch:root",
        sequence_no=0,
    )


def obligation(source: PuzzleState, conclusion: AssignmentAtom | ExclusionAtom) -> ProofObligation:
    negated = (
        AssignmentNegation(
            variable_id=conclusion.variable_id,
            value_id=conclusion.value_id,
        )
        if isinstance(conclusion, AssignmentAtom)
        else EliminationNegation(
            variable_id=conclusion.variable_id,
            value_id=conclusion.value_id,
        )
    )
    return ProofObligation(
        obligation_id=f"deductra:obligation:{conclusion.kind}:{conclusion.value_id}",
        puzzle_revision_id=source.puzzle_revision_id,
        source_state_hash=source.state_hash,
        claimed_conclusions=(conclusion,),
        negated_claim=negated,
    )


@pytest.mark.parametrize(
    ("expression", "givens", "conclusion"),
    (
        (
            Equal(
                left=Add(operands=(variable(A), variable(B))),
                right=constant(4),
            ),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            AssignmentAtom(variable_id=B, value_id=V3),
        ),
        (
            Equal(
                left=Multiply(operands=(variable(A), variable(B))),
                right=constant(3),
            ),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            AssignmentAtom(variable_id=B, value_id=V3),
        ),
        (
            Equal(
                left=ExactDivide(dividend=variable(B), divisor=variable(A)),
                right=constant(3),
            ),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            AssignmentAtom(variable_id=B, value_id=V3),
        ),
        (
            Equal(
                left=Modulo(dividend=variable(B), divisor=constant(2)),
                right=constant(0),
            ),
            (),
            AssignmentAtom(variable_id=B, value_id=V2),
        ),
        (
            And(
                operands=(
                    GreaterThan(left=variable(B), right=constant(2)),
                    LessThan(left=variable(B), right=constant(4)),
                )
            ),
            (),
            AssignmentAtom(variable_id=B, value_id=V3),
        ),
        (
            Or(
                operands=(
                    Equal(left=variable(B), right=constant(2)),
                    Equal(left=variable(B), right=constant(3)),
                )
            ),
            (),
            ExclusionAtom(variable_id=B, value_id=V1),
        ),
        (
            Implies(
                premise=Equal(left=variable(A), right=constant(1)),
                conclusion=Equal(left=variable(B), right=constant(3)),
            ),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            AssignmentAtom(variable_id=B, value_id=V3),
        ),
        (
            NotEqual(left=variable(B), right=constant(1)),
            (),
            ExclusionAtom(variable_id=B, value_id=V1),
        ),
    ),
)
def test_independent_backends_cross_verify_expression_catalogue(
    expression: BooleanExpression,
    givens: tuple[AssignmentAtom, ...],
    conclusion: AssignmentAtom | ExclusionAtom,
) -> None:
    specification = puzzle(expression, givens=givens)
    source = state(specification)
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        specification, source, obligation(source, conclusion)
    )
    assert decision.status is VerificationStatus.CROSS_VERIFIED
    assert {item.result for item in decision.certificates} == {"unsat"}
    assert {item.encoding_version for item in decision.certificates} == {
        "finite-domain-arithmetic-v1"
    }


def test_arithmetic_counterexample_is_rejected_by_both_backends() -> None:
    specification = puzzle(Equal(left=variable(B), right=constant(3)))
    source = state(specification)
    false_claim = AssignmentAtom(variable_id=B, value_id=V2)
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        specification, source, obligation(source, false_claim)
    )
    assert decision.status is VerificationStatus.REJECTED
    assert {item.result for item in decision.certificates} == {"sat"}


def test_zero_solution_source_cannot_prove_an_arbitrary_claim() -> None:
    specification = puzzle(Equal(left=variable(B), right=constant(4)))
    source = state(specification)
    arbitrary_claim = AssignmentAtom(variable_id=B, value_id=V1)
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        specification, source, obligation(source, arbitrary_claim)
    )
    assert decision.status is VerificationStatus.REJECTED
    assert {item.result for item in decision.certificates} == {"invalid"}


def test_verified_human_loop_uses_arithmetic_without_backend_bypass() -> None:
    specification = puzzle(
        Equal(left=variable(B), right=constant(3)),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    engine = HumanReasoningEngine(
        logic_equations_rules(),
        VerifiedRuleAuthority(
            CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
        ),
    )
    trace = engine.solve(
        specification,
        source,
        HumanSolveContext(
            trace_id="deductra:trace:logic-equations-backend-test",
            correlation_id="deductra:correlation:logic-equations-backend-test",
            producer=ProducerRef(
                producer_id="deductra:producer:logic-equations-rules",
                kind="rule_engine",
                version="1.0.0",
            ),
            occurred_at=NOW,
            previous_event_hash="a" * 64,
        ),
    )
    assert trace.status is HumanSolveStatus.SOLVED
    assert trace.events
    assert all(attempt.verification_status.value == "cross_verified" for attempt in trace.attempts)


def test_unimplemented_constraint_kind_fails_closed_in_both_backends() -> None:
    specification = PuzzleSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:unsupported-encoding-test",
            revision_id="deductra:revision:unsupported-encoding-test:1",
            family_id="unsupported-test",
            schema_version="1.0.0",
            title="Unsupported constraint fixture",
            source_kind="user",
            created_at=NOW,
        ),
        domains=(
            Domain(
                domain_id=DOMAIN,
                values=(
                    DomainValue(value_id=V1, label="1", ordinal=1, numeric_value=1),
                    DomainValue(value_id=V2, label="2", ordinal=2, numeric_value=2),
                ),
                ordered=True,
            ),
        ),
        variables=tuple(
            Variable(
                variable_id=item,
                label=item.rsplit(":", 1)[1].upper(),
                domain_id=DOMAIN,
                role="arithmetic",
            )
            for item in (A, B)
        ),
        constraints=(
            OrderConstraint(
                constraint_id="deductra:constraint:unsupported-order",
                label="A before B",
                before_variable_id=A,
                after_variable_id=B,
            ),
        ),
        clues=(),
        givens=(),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )
    source = state(specification)
    claim = AssignmentAtom(variable_id=A, value_id=V1)
    proof = obligation(source, claim)
    certificates = tuple(
        backend.verify(specification, source, proof, timeout_ms=5_000)
        for backend in (Z3ProofBackend(), CpSatProofBackend())
    )
    assert {item.result for item in certificates} == {"invalid"}
