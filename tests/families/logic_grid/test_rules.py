"""Acceptance tests for FAM-LG-002 deterministic human rules."""

from __future__ import annotations

from datetime import UTC, datetime

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    BooleanExpression,
    Constant,
    Equal,
    LessThan,
    NotEqual,
    Or,
    Subtract,
    VariableReference,
)
from deductra.domain.puzzle import Clue, DisplaySpec, ProvenanceBundle, PuzzleIdentity
from deductra.domain.serialization import canonical_json
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_grid import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridCategory,
    LogicGridSpec,
    discover_logic_grid_applications,
    logic_grid_rules,
)
from deductra.families.logic_grid.rules import (
    AssociationRule,
    CategoryBijectionRule,
    ClueCompletionRule,
    LogicGridTechnique,
)
from deductra.reasoning.rules import discover_rule_applications
from deductra.reasoning.state import PuzzleState, build_state, create_initial_state

A = "deductra:variable:logic-grid:people:1"
B = "deductra:variable:logic-grid:people:2"
C = "deductra:variable:logic-grid:exhibits:1"
D = "deductra:variable:logic-grid:exhibits:2"
V1 = "deductra:value:logic-grid:days:1"
V2 = "deductra:value:logic-grid:days:2"
V3 = "deductra:value:logic-grid:days:3"
CLUE_CONSTRAINT = "deductra:constraint:logic-grid:rule-test"


def variable(variable_id: str) -> VariableReference:
    return VariableReference(variable_id=variable_id)


def puzzle(
    expression: BooleanExpression,
    *,
    givens: tuple[AssignmentAtom, ...] = (),
) -> LogicGridSpec:
    """Build a non-Golden three-by-three rule fixture."""
    category_data = (
        ("people", "People", ("Ada", "Ben", "Cleo"), False),
        ("exhibits", "Exhibits", ("Kite", "Loom", "Mask"), False),
        ("days", "Days", ("Day 1", "Day 2", "Day 3"), True),
    )
    domains = tuple(
        Domain(
            domain_id=f"deductra:domain:logic-grid:{category_id}",
            values=tuple(
                DomainValue(
                    value_id=f"deductra:value:logic-grid:{category_id}:{index}",
                    label=label,
                    ordinal=index if ordered else None,
                    numeric_value=index if ordered else None,
                )
                for index, label in enumerate(labels, start=1)
            ),
            ordered=ordered,
            distinct_by_default=True,
        )
        for category_id, _, labels, ordered in category_data
    )
    categories = tuple(
        LogicGridCategory(
            category_id=f"deductra:category:logic-grid:{category_id}",
            label=label,
            domain_id=domain.domain_id,
            variable_ids=tuple(
                f"deductra:variable:logic-grid:{category_id}:{index}" for index in range(1, 4)
            ),
        )
        for (category_id, label, _, _), domain in zip(category_data, domains, strict=True)
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
            puzzle_id="deductra:puzzle:logic-grid-rule-test",
            revision_id="deductra:revision:logic-grid-rule-test:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title="Logic Grid rule fixture",
            source_kind="user",
            created_at=datetime(2026, 7, 19, tzinfo=UTC),
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
                label="Normalized rule fixture clue",
                source_clue_id="deductra:clue:logic-grid:rule-test",
                expression=expression,
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:logic-grid:rule-test",
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
        state_id="deductra:state:logic-grid-rule-test",
        branch_id="deductra:branch:root",
        sequence_no=0,
    )


def test_direct_match_proposes_an_explainable_assignment() -> None:
    specification = puzzle(
        Equal(left=variable(A), right=variable(C)),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    candidates = AssociationRule().find_applications(specification, source)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.premises == (AssignmentAtom(variable_id=A, value_id=V1),)
    proposal = AssociationRule().apply(candidate, source)
    assert proposal.conclusions == (AssignmentAtom(variable_id=C, value_id=V1),)
    assert proposal.supporting_constraints == (CLUE_CONSTRAINT,)


def test_direct_exclusion_uses_the_fixed_association_as_its_premise() -> None:
    specification = puzzle(
        NotEqual(left=variable(A), right=variable(C)),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    candidates = AssociationRule().find_applications(specification, source)
    assert len(candidates) == 1
    assert AssociationRule().apply(candidates[0], source).conclusions == (
        ExclusionAtom(variable_id=C, value_id=V1),
    )


def test_category_bijection_eliminates_an_occupied_row() -> None:
    specification = puzzle(
        Equal(left=variable(A), right=variable(C)),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    candidates = CategoryBijectionRule().find_applications(specification, source)
    conclusions = {
        canonical_json(CategoryBijectionRule().apply(item, source).conclusions[0])
        for item in candidates
    }
    assert conclusions == {
        canonical_json(ExclusionAtom(variable_id=B, value_id=V1)),
        canonical_json(
            ExclusionAtom(variable_id="deductra:variable:logic-grid:people:3", value_id=V1)
        ),
    }


def test_category_bijection_assigns_a_row_with_disclosed_exclusions() -> None:
    specification = puzzle(Equal(left=variable(A), right=variable(C)))
    source = state(specification)
    third_person = "deductra:variable:logic-grid:people:3"
    asserted = (
        *source.asserted_atoms,
        ExclusionAtom(variable_id=B, value_id=V1),
        ExclusionAtom(variable_id=third_person, value_id=V1),
    )
    narrowed = build_state(
        state_id="deductra:state:logic-grid-rule-test:narrowed",
        puzzle_revision_id=source.puzzle_revision_id,
        sequence_no=1,
        branch_id=source.branch_id,
        candidate_domains={
            **source.candidate_domains,
            B: frozenset((V2, V3)),
            third_person: frozenset((V2, V3)),
        },
        asserted_atoms=frozenset(asserted),
        rejected_atoms=source.rejected_atoms,
        active_constraint_ids=source.active_constraint_ids,
        contradiction_ids=(),
    )
    rule = CategoryBijectionRule()
    assignments = [
        item
        for item in rule.find_applications(specification, narrowed)
        if rule.apply(item, narrowed).conclusions == (AssignmentAtom(variable_id=A, value_id=V1),)
    ]
    assert len(assignments) == 1
    assert assignments[0].premises == (
        ExclusionAtom(variable_id=B, value_id=V1),
        ExclusionAtom(variable_id=third_person, value_id=V1),
    )


def test_ordering_uses_only_disclosed_domain_bounds() -> None:
    specification = puzzle(LessThan(left=variable(A), right=variable(C)))
    source = state(specification)
    rule = ClueCompletionRule(LogicGridTechnique.ORDERING, "Ordered association")
    conclusions = {
        canonical_json(rule.apply(item, source).conclusions[0])
        for item in rule.find_applications(specification, source)
    }
    assert conclusions == {
        canonical_json(ExclusionAtom(variable_id=A, value_id=V3)),
        canonical_json(ExclusionAtom(variable_id=C, value_id=V1)),
    }


def test_exact_difference_completion_uses_only_fixed_premises() -> None:
    specification = puzzle(
        Equal(
            left=Subtract(left=variable(A), right=variable(C)),
            right=Constant(value=1),
        ),
        givens=(AssignmentAtom(variable_id=A, value_id=V3),),
    )
    source = state(specification)
    rule = ClueCompletionRule(LogicGridTechnique.NUMERIC_RELATION, "Numeric relation")
    candidates = rule.find_applications(specification, source)
    assert len(candidates) == 1
    assert candidates[0].premises == (AssignmentAtom(variable_id=A, value_id=V3),)
    assert rule.apply(candidates[0], source).conclusions == (
        AssignmentAtom(variable_id=C, value_id=V2),
    )


def test_compound_clue_completion_has_a_distinct_technique() -> None:
    specification = puzzle(
        Or(
            operands=(
                Equal(left=variable(A), right=variable(B)),
                Equal(left=variable(A), right=variable(C)),
            )
        ),
        givens=(
            AssignmentAtom(variable_id=A, value_id=V1),
            AssignmentAtom(variable_id=B, value_id=V2),
        ),
    )
    source = state(specification)
    rule = ClueCompletionRule(LogicGridTechnique.COMPOUND_LOGIC, "Compound clue")
    candidates = rule.find_applications(specification, source)
    assert len(candidates) == 1
    assert rule.apply(candidates[0], source).conclusions == (
        AssignmentAtom(variable_id=C, value_id=V1),
    )


def test_multi_variable_numeric_enumeration_is_not_hidden_in_a_rule() -> None:
    specification = puzzle(
        Equal(
            left=Subtract(left=variable(A), right=variable(C)),
            right=Constant(value=1),
        )
    )
    source = state(specification)
    rule = ClueCompletionRule(LogicGridTechnique.NUMERIC_RELATION, "Numeric relation")
    assert rule.find_applications(specification, source) == ()


def test_family_discovery_is_independent_of_catalogue_order() -> None:
    specification = puzzle(
        NotEqual(left=variable(A), right=variable(C)),
        givens=(AssignmentAtom(variable_id=A, value_id=V1),),
    )
    source = state(specification)
    rules = logic_grid_rules()
    forward = discover_logic_grid_applications(specification, source)
    reverse = discover_rule_applications(specification, source, tuple(reversed(rules)))
    assert forward == reverse
