"""Differential acceptance tests for FAM-LG-003 backend encodings."""

from __future__ import annotations

from datetime import UTC, datetime
from fractions import Fraction

import pytest

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    And,
    BooleanExpression,
    Cardinality,
    Constant,
    Equal,
    Equivalent,
    Implies,
    LessThan,
    Not,
    NotEqual,
    Or,
    Subtract,
    VariableReference,
    Xor,
)
from deductra.domain.puzzle import Clue, DisplaySpec, ProvenanceBundle, PuzzleIdentity
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_grid import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridCategory,
    LogicGridSpec,
    logic_grid_rules,
)
from deductra.families.logic_grid.rules import ClueCompletionRule, LogicGridTechnique
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

NOW = datetime(2026, 7, 19, 18, 0, tzinfo=UTC)
A = "deductra:variable:logic-grid:people:1"
B = "deductra:variable:logic-grid:people:2"
C = "deductra:variable:logic-grid:exhibits:1"
D = "deductra:variable:logic-grid:exhibits:2"
V1 = "deductra:value:logic-grid:slots:1"
V2 = "deductra:value:logic-grid:slots:2"
V3 = "deductra:value:logic-grid:slots:3"
CLUE_CONSTRAINT = "deductra:constraint:logic-grid:backend-test"


def variable(variable_id: str) -> VariableReference:
    return VariableReference(variable_id=variable_id)


def puzzle(
    expression: BooleanExpression,
    *,
    size: int = 3,
    givens: tuple[AssignmentAtom, ...] = (),
    anchor_numeric_values: tuple[int | Fraction, ...] | None = (1, 2, 3),
) -> LogicGridSpec:
    """Build a synthetic Logic Grid fixture, never product reference content."""
    if anchor_numeric_values is not None and len(anchor_numeric_values) != size:
        raise ValueError("anchor numeric values must match fixture size")
    category_data = (
        ("people", "People", tuple(f"Person {index}" for index in range(1, size + 1))),
        ("exhibits", "Exhibits", tuple(f"Exhibit {index}" for index in range(1, size + 1))),
        ("slots", "Slots", tuple(f"Slot {index}" for index in range(1, size + 1))),
    )
    domains = tuple(
        Domain(
            domain_id=f"deductra:domain:logic-grid:{category_id}",
            values=tuple(
                DomainValue(
                    value_id=f"deductra:value:logic-grid:{category_id}:{index}",
                    label=label,
                    ordinal=index if category_id == "slots" else None,
                    numeric_value=(
                        anchor_numeric_values[index - 1]
                        if category_id == "slots" and anchor_numeric_values is not None
                        else None
                    ),
                )
                for index, label in enumerate(labels, start=1)
            ),
            ordered=category_id == "slots",
            distinct_by_default=True,
        )
        for category_id, _, labels in category_data
    )
    categories = tuple(
        LogicGridCategory(
            category_id=f"deductra:category:logic-grid:{category_id}",
            label=label,
            domain_id=domain.domain_id,
            variable_ids=tuple(
                f"deductra:variable:logic-grid:{category_id}:{index}"
                for index in range(1, size + 1)
            ),
        )
        for (category_id, label, _), domain in zip(category_data, domains, strict=True)
    )
    anchor_domain = domains[-1]
    variables = tuple(
        Variable(
            variable_id=variable_id,
            label=value.label,
            domain_id=anchor_domain.domain_id,
            role="entity_assignment",
        )
        for category, domain in zip(categories, domains, strict=True)
        for variable_id, value in zip(category.variable_ids, domain.values, strict=True)
    )
    anchor_givens = tuple(
        AssignmentAtom(variable_id=variable_id, value_id=value.value_id)
        for variable_id, value in zip(
            categories[-1].variable_ids, anchor_domain.values, strict=True
        )
    )
    return LogicGridSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:logic-grid-backend-test",
            revision_id="deductra:revision:logic-grid-backend-test:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title="Logic Grid backend fixture",
            source_kind="user",
            created_at=NOW,
        ),
        domains=domains,
        variables=variables,
        constraints=(
            *(
                AllDifferentConstraint(
                    constraint_id=f"deductra:constraint:logic-grid:{index}:bijection",
                    label=f"{category.label} items occupy different rows",
                    variable_ids=category.variable_ids,
                )
                for index, category in enumerate(categories, start=1)
            ),
            ArithmeticConstraint(
                constraint_id=CLUE_CONSTRAINT,
                label="Normalized backend fixture clue",
                source_clue_id="deductra:clue:logic-grid:backend-test",
                expression=expression,
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:logic-grid:backend-test",
                text="A normalized Logic Grid clue.",
                constraint_ids=(CLUE_CONSTRAINT,),
                locale="en",
            ),
        ),
        givens=(*anchor_givens, *givens),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
        categories=categories,
        anchor_category_id=categories[-1].category_id,
    )


def state(specification: LogicGridSpec) -> PuzzleState:
    return create_initial_state(
        specification,
        state_id="deductra:state:logic-grid-backend-test",
        branch_id="deductra:branch:root",
        sequence_no=0,
    )


def obligation(source: PuzzleState, conclusion: AssignmentAtom | ExclusionAtom) -> ProofObligation:
    negated = (
        AssignmentNegation(variable_id=conclusion.variable_id, value_id=conclusion.value_id)
        if isinstance(conclusion, AssignmentAtom)
        else EliminationNegation(
            variable_id=conclusion.variable_id,
            value_id=conclusion.value_id,
        )
    )
    return ProofObligation(
        obligation_id=f"deductra:obligation:logic-grid:{conclusion.kind}:{conclusion.value_id}",
        puzzle_revision_id=source.puzzle_revision_id,
        source_state_hash=source.state_hash,
        claimed_conclusions=(conclusion,),
        negated_claim=negated,
    )


@pytest.mark.parametrize(
    ("expression", "givens", "conclusion", "numeric_values"),
    (
        (
            Equal(left=variable(A), right=variable(C)),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            AssignmentAtom(variable_id=C, value_id=V1),
            None,
        ),
        (
            NotEqual(left=variable(A), right=variable(C)),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            ExclusionAtom(variable_id=C, value_id=V1),
            None,
        ),
        (
            LessThan(left=variable(A), right=variable(C)),
            (AssignmentAtom(variable_id=A, value_id=V2),),
            AssignmentAtom(variable_id=C, value_id=V3),
            None,
        ),
        (
            And(
                operands=(
                    Equal(left=variable(A), right=variable(C)),
                    Equal(left=variable(B), right=variable(D)),
                )
            ),
            (
                AssignmentAtom(variable_id=A, value_id=V1),
                AssignmentAtom(variable_id=C, value_id=V1),
                AssignmentAtom(variable_id=B, value_id=V2),
            ),
            AssignmentAtom(variable_id=D, value_id=V2),
            None,
        ),
        (
            Or(
                operands=(
                    Equal(left=variable(A), right=variable(C)),
                    Equal(left=variable(A), right=variable(D)),
                )
            ),
            (
                AssignmentAtom(variable_id=A, value_id=V1),
                AssignmentAtom(variable_id=C, value_id=V2),
            ),
            AssignmentAtom(variable_id=D, value_id=V1),
            None,
        ),
        (
            Not(operand=Equal(left=variable(A), right=variable(C))),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            ExclusionAtom(variable_id=C, value_id=V1),
            None,
        ),
        (
            Xor(
                left=Equal(left=variable(A), right=variable(C)),
                right=Equal(left=variable(B), right=variable(D)),
            ),
            (
                AssignmentAtom(variable_id=A, value_id=V1),
                AssignmentAtom(variable_id=C, value_id=V1),
                AssignmentAtom(variable_id=B, value_id=V2),
            ),
            ExclusionAtom(variable_id=D, value_id=V2),
            None,
        ),
        (
            Implies(
                premise=Equal(left=variable(A), right=variable(C)),
                conclusion=Equal(left=variable(B), right=variable(D)),
            ),
            (
                AssignmentAtom(variable_id=A, value_id=V1),
                AssignmentAtom(variable_id=C, value_id=V1),
                AssignmentAtom(variable_id=B, value_id=V2),
            ),
            AssignmentAtom(variable_id=D, value_id=V2),
            None,
        ),
        (
            Equivalent(
                left=Equal(left=variable(A), right=variable(C)),
                right=Equal(left=variable(B), right=variable(D)),
            ),
            (
                AssignmentAtom(variable_id=A, value_id=V1),
                AssignmentAtom(variable_id=C, value_id=V1),
                AssignmentAtom(variable_id=B, value_id=V2),
            ),
            AssignmentAtom(variable_id=D, value_id=V2),
            None,
        ),
        (
            Cardinality(
                operands=(
                    Equal(left=variable(A), right=variable(C)),
                    Equal(left=variable(B), right=variable(D)),
                ),
                minimum=1,
                maximum=1,
            ),
            (
                AssignmentAtom(variable_id=A, value_id=V1),
                AssignmentAtom(variable_id=C, value_id=V1),
                AssignmentAtom(variable_id=B, value_id=V2),
            ),
            ExclusionAtom(variable_id=D, value_id=V2),
            None,
        ),
        (
            Equal(
                left=Subtract(left=variable(A), right=variable(C)),
                right=Constant(value=Fraction(1, 1)),
            ),
            (AssignmentAtom(variable_id=A, value_id=V3),),
            AssignmentAtom(variable_id=C, value_id=V2),
            (Fraction(1, 2), Fraction(3, 2), Fraction(5, 2)),
        ),
    ),
)
def test_independent_backends_cross_verify_logic_grid_catalogue(
    expression: BooleanExpression,
    givens: tuple[AssignmentAtom, ...],
    conclusion: AssignmentAtom | ExclusionAtom,
    numeric_values: tuple[int | Fraction, ...] | None,
) -> None:
    specification = puzzle(
        expression,
        givens=givens,
        anchor_numeric_values=numeric_values,
    )
    source = state(specification)
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        specification,
        source,
        obligation(source, conclusion),
    )
    assert decision.status is VerificationStatus.CROSS_VERIFIED
    assert {item.result for item in decision.certificates} == {"unsat"}
    assert {item.encoding_version for item in decision.certificates} == {
        "finite-domain-logic-grid-v1"
    }


def test_counterexample_is_rejected_by_both_backends() -> None:
    specification = puzzle(
        Equal(left=variable(A), right=variable(C)),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
        anchor_numeric_values=None,
    )
    source = state(specification)
    false_claim = AssignmentAtom(variable_id=C, value_id=V2)
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        specification, source, obligation(source, false_claim)
    )
    assert decision.status is VerificationStatus.REJECTED
    assert {item.result for item in decision.certificates} == {"sat"}


def test_rule_and_backends_keep_ordinal_order_separate_from_numeric_values() -> None:
    specification = puzzle(
        LessThan(left=variable(A), right=variable(C)),
        givens=(AssignmentAtom(variable_id=A, value_id=V2),),
        anchor_numeric_values=(100, 10, 50),
    )
    source = state(specification)
    rule = ClueCompletionRule(LogicGridTechnique.ORDERING, "Ordered association")
    applications = rule.find_applications(specification, source)
    assert len(applications) == 1
    conclusion = rule.apply(applications[0], source).conclusions[0]
    assert conclusion == AssignmentAtom(variable_id=C, value_id=V3)
    assert isinstance(conclusion, (AssignmentAtom, ExclusionAtom))

    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        specification,
        source,
        obligation(source, conclusion),
    )
    assert decision.status is VerificationStatus.CROSS_VERIFIED


def test_unsatisfiable_source_cannot_prove_an_arbitrary_claim() -> None:
    specification = puzzle(
        Equal(left=variable(A), right=variable(C)),
        givens=(
            AssignmentAtom(variable_id=A, value_id=V1),
            AssignmentAtom(variable_id=C, value_id=V2),
        ),
        anchor_numeric_values=None,
    )
    source = state(specification)
    claim = AssignmentAtom(variable_id=B, value_id=V3)
    decision = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend())).verify(
        specification, source, obligation(source, claim)
    )
    assert decision.status is VerificationStatus.REJECTED
    assert {item.result for item in decision.certificates} == {"invalid"}


def test_cpsat_truth_table_fails_closed_above_the_reviewed_limit() -> None:
    size = 11
    expression = Cardinality(
        operands=tuple(
            Equal(
                left=variable(f"deductra:variable:logic-grid:people:{index}"),
                right=variable(f"deductra:variable:logic-grid:exhibits:{index}"),
            )
            for index in range(1, 7)
        ),
        minimum=1,
        maximum=3,
    )
    specification = puzzle(
        expression,
        size=size,
        anchor_numeric_values=None,
    )
    source = state(specification)
    claim = AssignmentAtom(
        variable_id="deductra:variable:logic-grid:people:1",
        value_id="deductra:value:logic-grid:slots:1",
    )
    certificate = CpSatProofBackend().verify(
        specification,
        source,
        obligation(source, claim),
        timeout_ms=5_000,
    )
    assert certificate.result == "invalid"
    assert certificate.encoding_version == "finite-domain-logic-grid-v1"


def test_verified_human_loop_uses_logic_grid_backends_without_bypass() -> None:
    specification = puzzle(
        Equal(left=variable(A), right=variable(C)),
        size=2,
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
        anchor_numeric_values=None,
    )
    source = state(specification)
    engine = HumanReasoningEngine(
        logic_grid_rules(),
        VerifiedRuleAuthority(
            CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
        ),
    )
    trace = engine.solve(
        specification,
        source,
        HumanSolveContext(
            trace_id="deductra:trace:logic-grid-backend-test",
            correlation_id="deductra:correlation:logic-grid-backend-test",
            producer=ProducerRef(
                producer_id="deductra:producer:logic-grid-rules",
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
