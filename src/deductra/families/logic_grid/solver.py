"""Ordered human-rule catalogue and discovery facade for Logic Grid."""

from deductra.families.logic_grid.rules import (
    AssociationRule,
    CategoryBijectionRule,
    ClueCompletionRule,
    LogicGridTechnique,
)
from deductra.families.logic_grid.specification import LogicGridSpec
from deductra.reasoning.rules import (
    ReasoningRule,
    RuleApplicationCandidate,
    discover_rule_applications,
)
from deductra.reasoning.state import PuzzleState


def logic_grid_rules() -> tuple[ReasoningRule, ...]:
    """Return the complete ordered FAM-LG-002 human-rule catalogue."""
    return (
        AssociationRule(),
        CategoryBijectionRule(),
        ClueCompletionRule(LogicGridTechnique.ORDERING, "Ordered association"),
        ClueCompletionRule(LogicGridTechnique.NUMERIC_RELATION, "Numeric relation"),
        ClueCompletionRule(LogicGridTechnique.COMPOUND_LOGIC, "Compound clue"),
    )


def discover_logic_grid_applications(
    puzzle: LogicGridSpec,
    state: PuzzleState,
) -> tuple[RuleApplicationCandidate, ...]:
    """Discover all disclosed family-rule applications in canonical order."""
    return discover_rule_applications(puzzle, state, logic_grid_rules())
