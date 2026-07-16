"""Ordered human-rule catalogue and discovery facade for Logic Equations."""

from __future__ import annotations

from deductra.families.logic_equations.rules import (
    AllDifferentPropagationRule,
    ConstraintPropagationRule,
    LogicEquationsTechnique,
)
from deductra.families.logic_equations.specification import LogicEquationsSpec
from deductra.reasoning.rules import (
    ReasoningRule,
    RuleApplicationCandidate,
    discover_rule_applications,
)
from deductra.reasoning.state import PuzzleState


def logic_equations_rules() -> tuple[ReasoningRule, ...]:
    """Return the complete ordered FAM-LE-002 human-rule catalogue."""
    return (
        ConstraintPropagationRule(
            LogicEquationsTechnique.DIRECT_RELATION,
            "Direct relation and domain bound",
        ),
        AllDifferentPropagationRule(),
        ConstraintPropagationRule(
            LogicEquationsTechnique.ARITHMETIC,
            "Arithmetic relation",
        ),
        ConstraintPropagationRule(
            LogicEquationsTechnique.PARITY_DIVISIBILITY,
            "Parity and divisibility",
        ),
        ConstraintPropagationRule(
            LogicEquationsTechnique.DISJUNCTION,
            "Disjunction elimination",
        ),
        ConstraintPropagationRule(
            LogicEquationsTechnique.IMPLICATION,
            "Conditional implication",
        ),
    )


def discover_logic_equations_applications(
    puzzle: LogicEquationsSpec,
    state: PuzzleState,
) -> tuple[RuleApplicationCandidate, ...]:
    """Discover all disclosed family-rule applications in canonical order."""
    return discover_rule_applications(puzzle, state, logic_equations_rules())
