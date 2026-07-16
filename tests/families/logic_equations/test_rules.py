"""Acceptance tests for FAM-LE-002 deterministic human rules."""

from __future__ import annotations

from datetime import UTC, datetime

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    Add,
    BooleanExpression,
    Constant,
    Equal,
    GreaterThan,
    Implies,
    Modulo,
    Or,
    VariableReference,
)
from deductra.domain.puzzle import (
    Clue,
    DisplaySpec,
    ProvenanceBundle,
    PuzzleIdentity,
)
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_equations import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicEquationsSpec,
    discover_logic_equations_applications,
    logic_equations_rules,
)
from deductra.families.logic_equations.rules import (
    AllDifferentPropagationRule,
    ConstraintPropagationRule,
    LogicEquationsTechnique,
)
from deductra.reasoning.rules import discover_rule_applications
from deductra.reasoning.state import PuzzleState, create_initial_state

DOMAIN = "deductra:domain:logic-equations-rule-test"
A = "deductra:variable:a"
B = "deductra:variable:b"
C = "deductra:variable:c"
V1 = "deductra:value:1"
V2 = "deductra:value:2"
V3 = "deductra:value:3"
ARITHMETIC_CONSTRAINT = "deductra:constraint:arithmetic"


def variable(variable_id: str) -> VariableReference:
    return VariableReference(variable_id=variable_id)


def constant(value: int) -> Constant:
    return Constant(value=value)


def puzzle(
    expression: BooleanExpression,
    *,
    givens: tuple[AssignmentAtom, ...] = (),
) -> LogicEquationsSpec:
    variables = tuple(
        Variable(
            variable_id=variable_id,
            label=variable_id.rsplit(":", 1)[1].upper(),
            domain_id=DOMAIN,
            role="arithmetic",
        )
        for variable_id in (A, B, C)
    )
    return LogicEquationsSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:logic-equations-rule-test",
            revision_id="deductra:revision:logic-equations-rule-test:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title="Rule test fixture",
            source_kind="user",
            created_at=datetime(2026, 7, 16, tzinfo=UTC),
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
        variables=variables,
        constraints=(
            AllDifferentConstraint(
                constraint_id="deductra:constraint:all-different",
                label="All values differ",
                variable_ids=(A, B, C),
            ),
            ArithmeticConstraint(
                constraint_id=ARITHMETIC_CONSTRAINT,
                label="Arithmetic clue",
                source_clue_id="deductra:clue:arithmetic",
                expression=expression,
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:arithmetic",
                text="A normalized arithmetic clue.",
                constraint_ids=(ARITHMETIC_CONSTRAINT,),
                locale="en",
            ),
        ),
        givens=givens,
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def state(specification: LogicEquationsSpec) -> PuzzleState:
    return create_initial_state(
        specification,
        state_id="deductra:state:logic-equations-rule-test",
        branch_id="deductra:branch:root",
        sequence_no=0,
    )


def test_direct_equality_proposes_an_explainable_assignment() -> None:
    specification = puzzle(Equal(left=variable(A), right=constant(1)))
    source = state(specification)
    candidates = discover_logic_equations_applications(specification, source)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.rule.rule_id.endswith(":direct_relation")
    proposal = logic_equations_rules()[0].apply(candidate, source)
    assert proposal.conclusions == (AssignmentAtom(variable_id=A, value_id=V1),)
    assert proposal.supporting_constraints == (ARITHMETIC_CONSTRAINT,)


def test_order_bound_eliminates_only_the_impossible_value() -> None:
    specification = puzzle(GreaterThan(left=variable(B), right=constant(1)))
    source = state(specification)
    candidates = ConstraintPropagationRule(
        LogicEquationsTechnique.DIRECT_RELATION,
        "Direct relation",
    ).find_applications(specification, source)
    assert tuple(item.tie_break_key for item in candidates) == (
        '{"kind":"exclusion","value_id":"deductra:value:1","variable_id":"deductra:variable:b"}',
    )


def test_arithmetic_completion_uses_only_fixed_premises() -> None:
    specification = puzzle(
        Equal(
            left=Add(operands=(variable(A), variable(B))),
            right=constant(4),
        ),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    rule = ConstraintPropagationRule(
        LogicEquationsTechnique.ARITHMETIC,
        "Arithmetic relation",
    )
    candidates = rule.find_applications(specification, source)
    assert len(candidates) == 1
    assert candidates[0].premises == (AssignmentAtom(variable_id=A, value_id=V1),)
    proposal = rule.apply(candidates[0], source)
    assert proposal.conclusions == (AssignmentAtom(variable_id=B, value_id=V3),)


def test_parity_disjunction_and_implication_have_distinct_techniques() -> None:
    cases = (
        (
            Equal(
                left=Modulo(dividend=variable(B), divisor=constant(2)),
                right=constant(0),
            ),
            (),
            LogicEquationsTechnique.PARITY_DIVISIBILITY,
            AssignmentAtom(variable_id=B, value_id=V2),
        ),
        (
            Or(
                operands=(
                    Equal(left=variable(B), right=constant(2)),
                    Equal(left=variable(B), right=constant(3)),
                )
            ),
            (),
            LogicEquationsTechnique.DISJUNCTION,
            ExclusionAtom(variable_id=B, value_id=V1),
        ),
        (
            Implies(
                premise=Equal(left=variable(A), right=constant(1)),
                conclusion=Equal(left=variable(B), right=constant(3)),
            ),
            (AssignmentAtom(variable_id=A, value_id=V1),),
            LogicEquationsTechnique.IMPLICATION,
            AssignmentAtom(variable_id=B, value_id=V3),
        ),
    )
    for expression, givens, technique, expected in cases:
        specification = puzzle(expression, givens=givens)
        source = state(specification)
        rule = ConstraintPropagationRule(technique, technique.value)
        candidates = rule.find_applications(specification, source)
        assert len(candidates) == 1
        assert rule.apply(candidates[0], source).conclusions == (expected,)


def test_all_different_propagation_cites_the_assignment_premise() -> None:
    specification = puzzle(
        GreaterThan(left=variable(B), right=constant(1)),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    candidates = AllDifferentPropagationRule().find_applications(specification, source)
    assert len(candidates) == 2
    assert {item.affected_variables for item in candidates} == {(B,), (C,)}
    assert all(
        item.premises == (AssignmentAtom(variable_id=A, value_id=V1),) for item in candidates
    )


def test_rule_discovery_is_independent_of_catalogue_order() -> None:
    specification = puzzle(
        Equal(
            left=Add(operands=(variable(A), variable(B))),
            right=constant(4),
        ),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    rules = logic_equations_rules()
    forward = discover_rule_applications(specification, source, rules)
    reverse = discover_rule_applications(specification, source, tuple(reversed(rules)))
    assert forward == reverse


def test_multi_variable_enumeration_is_not_hidden_inside_a_human_rule() -> None:
    specification = puzzle(
        Equal(
            left=Add(operands=(variable(A), variable(B))),
            right=constant(4),
        )
    )
    source = state(specification)
    rule = ConstraintPropagationRule(
        LogicEquationsTechnique.ARITHMETIC,
        "Arithmetic relation",
    )
    assert rule.find_applications(specification, source) == ()
