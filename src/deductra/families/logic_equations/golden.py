"""Canonical Golden fixtures for Logic Equations."""

from __future__ import annotations

from datetime import UTC, datetime

from deductra.domain.atoms import AssignmentAtom
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import Add, Constant, Equal, GreaterThan, VariableReference
from deductra.domain.puzzle import (
    Clue,
    DisplaySpec,
    ProvenanceBundle,
    ProvenanceReference,
    PuzzleIdentity,
)
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_equations.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicEquationsSpec,
)

_DOMAIN = "deductra:domain:logic-equations:four-sigils"
_EMBER = "deductra:variable:four-sigils:ember"
_TIDE = "deductra:variable:four-sigils:tide"
_GALE = "deductra:variable:four-sigils:gale"
_STONE = "deductra:variable:four-sigils:stone"

FOUR_SIGILS_SOLUTION = (
    AssignmentAtom(variable_id=_EMBER, value_id="deductra:value:four-sigils:1"),
    AssignmentAtom(variable_id=_TIDE, value_id="deductra:value:four-sigils:2"),
    AssignmentAtom(variable_id=_GALE, value_id="deductra:value:four-sigils:3"),
    AssignmentAtom(variable_id=_STONE, value_id="deductra:value:four-sigils:4"),
)


def four_sigils() -> LogicEquationsSpec:
    """Return the fixed, handcrafted Logic Equations Golden Easy puzzle."""
    variables = (
        Variable(variable_id=_EMBER, label="Ember", domain_id=_DOMAIN, role="arithmetic"),
        Variable(variable_id=_TIDE, label="Tide", domain_id=_DOMAIN, role="arithmetic"),
        Variable(variable_id=_GALE, label="Gale", domain_id=_DOMAIN, role="arithmetic"),
        Variable(variable_id=_STONE, label="Stone", domain_id=_DOMAIN, role="arithmetic"),
    )
    all_different = "deductra:constraint:four-sigils:all-different"
    ember_is_one = "deductra:constraint:four-sigils:ember-is-one"
    tide_offset = "deductra:constraint:four-sigils:tide-offset"
    stone_above_gale = "deductra:constraint:four-sigils:stone-above-gale"
    return LogicEquationsSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:logic-equations:four-sigils",
            revision_id="deductra:revision:logic-equations:four-sigils:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title="The Four Sigils",
            author="Deductra Project",
            source_kind="golden",
            created_at=datetime(2026, 7, 16, tzinfo=UTC),
            metadata={
                "difficulty": "easy",
                "golden_version": "1.0.0",
            },
        ),
        domains=(
            Domain(
                domain_id=_DOMAIN,
                values=tuple(
                    DomainValue(
                        value_id=f"deductra:value:four-sigils:{value}",
                        label=str(value),
                        ordinal=value,
                        numeric_value=value,
                    )
                    for value in range(1, 5)
                ),
                ordered=True,
                distinct_by_default=True,
            ),
        ),
        variables=variables,
        constraints=(
            AllDifferentConstraint(
                constraint_id=all_different,
                label="Each sigil has a different number",
                variable_ids=tuple(variable.variable_id for variable in variables),
            ),
            ArithmeticConstraint(
                constraint_id=ember_is_one,
                label="Ember equals one",
                source_clue_id="deductra:clue:four-sigils:ember-is-one",
                expression=Equal(
                    left=VariableReference(variable_id=_EMBER),
                    right=Constant(value=1),
                ),
            ),
            ArithmeticConstraint(
                constraint_id=tide_offset,
                label="Tide is one above Ember",
                source_clue_id="deductra:clue:four-sigils:tide-offset",
                expression=Equal(
                    left=VariableReference(variable_id=_TIDE),
                    right=Add(
                        operands=(
                            VariableReference(variable_id=_EMBER),
                            Constant(value=1),
                        )
                    ),
                ),
            ),
            ArithmeticConstraint(
                constraint_id=stone_above_gale,
                label="Stone is above Gale",
                source_clue_id="deductra:clue:four-sigils:stone-above-gale",
                expression=GreaterThan(
                    left=VariableReference(variable_id=_STONE),
                    right=VariableReference(variable_id=_GALE),
                ),
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:four-sigils:ember-is-one",
                text="The Ember sigil is numbered 1.",
                constraint_ids=(ember_is_one,),
                locale="en",
            ),
            Clue(
                clue_id="deductra:clue:four-sigils:tide-offset",
                text="The Tide sigil is numbered one higher than the Ember sigil.",
                constraint_ids=(tide_offset,),
                locale="en",
            ),
            Clue(
                clue_id="deductra:clue:four-sigils:stone-above-gale",
                text="The Stone sigil has a higher number than the Gale sigil.",
                constraint_ids=(stone_above_gale,),
                locale="en",
            ),
        ),
        givens=(),
        display_spec=DisplaySpec(
            accessibility_labels=tuple(
                (variable.variable_id, f"{variable.label} sigil") for variable in variables
            )
        ),
        provenance=ProvenanceBundle(
            references=(
                ProvenanceReference(
                    provenance_id="deductra:provenance:four-sigils:original",
                    kind="entity",
                    label="Original Deductra Golden puzzle",
                ),
            )
        ),
    )
