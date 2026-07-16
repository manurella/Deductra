"""Logic Equations specialization of the common immutable puzzle contract."""

from __future__ import annotations

from pydantic import model_validator

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    Add,
    And,
    BooleanExpression,
    Constant,
    Equal,
    ExactDivide,
    GreaterThan,
    GreaterThanOrEqual,
    Implies,
    LessThan,
    LessThanOrEqual,
    Modulo,
    Multiply,
    Not,
    NotEqual,
    NumericExpression,
    Or,
    Subtract,
    VariableReference,
)
from deductra.domain.ids import VariableId
from deductra.domain.puzzle import PuzzleSpec

FAMILY_ID = "logic-equations"
SPEC_SCHEMA_VERSION = "1.0.0"

_ALLOWED_BOOLEAN_TYPES = (
    Equal,
    NotEqual,
    LessThan,
    LessThanOrEqual,
    GreaterThan,
    GreaterThanOrEqual,
    And,
    Or,
    Not,
    Implies,
)


class LogicEquationsSpec(PuzzleSpec):
    """A finite-domain, all-different arithmetic assignment puzzle."""

    @model_validator(mode="after")
    def validate_logic_equations_contract(self) -> LogicEquationsSpec:
        """Enforce the normalized v1 family specification."""
        if self.identity.family_id != FAMILY_ID:
            raise ValueError(f"family_id must be {FAMILY_ID!r}")
        if self.identity.schema_version != SPEC_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SPEC_SCHEMA_VERSION!r}")
        if len(self.domains) != 1:
            raise ValueError("Logic Equations requires exactly one value domain")

        domain = self.domains[0]
        if not domain.ordered or not domain.distinct_by_default:
            raise ValueError("the value domain must be ordered and distinct by default")
        if len(domain.values) < 2:
            raise ValueError("the value domain must contain at least two integers")

        expected_values = tuple(range(1, len(domain.values) + 1))
        numeric_values = tuple(value.numeric_value for value in domain.values)
        ordinals = tuple(value.ordinal for value in domain.values)
        if numeric_values != expected_values or ordinals != expected_values:
            raise ValueError("domain numeric values and ordinals must be the ordered range 1..n")

        if len(self.variables) != len(domain.values):
            raise ValueError("Logic Equations requires one variable for each domain value")
        if any(
            variable.domain_id != domain.domain_id or variable.role != "arithmetic"
            for variable in self.variables
        ):
            raise ValueError("all variables must be arithmetic variables in the value domain")
        labels = tuple(variable.label for variable in self.variables)
        if any(not label.strip() for label in labels) or len(labels) != len(set(labels)):
            raise ValueError("variable labels must be non-empty and unique")

        variable_ids = frozenset(variable.variable_id for variable in self.variables)
        value_ids = frozenset(value.value_id for value in domain.values)
        all_different = tuple(
            constraint
            for constraint in self.constraints
            if isinstance(constraint, AllDifferentConstraint)
        )
        arithmetic = tuple(
            constraint
            for constraint in self.constraints
            if isinstance(constraint, ArithmeticConstraint)
        )
        if len(all_different) != 1 or frozenset(all_different[0].variable_ids) != variable_ids:
            raise ValueError("one all-different constraint must cover every variable exactly once")
        if len(all_different[0].variable_ids) != len(variable_ids):
            raise ValueError("the all-different constraint cannot repeat variables")
        if len(arithmetic) + 1 != len(self.constraints) or not arithmetic:
            raise ValueError(
                "constraints must contain one all-different constraint and arithmetic clues"
            )

        for constraint in arithmetic:
            self._validate_boolean_expression(constraint.expression, variable_ids)

        arithmetic_ids = frozenset(constraint.constraint_id for constraint in arithmetic)
        clue_constraint_ids = tuple(
            constraint_id for clue in self.clues for constraint_id in clue.constraint_ids
        )
        if frozenset(clue_constraint_ids) != arithmetic_ids:
            raise ValueError(
                "clues must cover every arithmetic constraint and no implicit constraint"
            )
        if len(clue_constraint_ids) != len(arithmetic_ids):
            raise ValueError("each arithmetic constraint must be linked from exactly one clue")
        if any(not clue.text.strip() or len(clue.constraint_ids) != 1 for clue in self.clues):
            raise ValueError(
                "each clue must contain text and link exactly one arithmetic constraint"
            )
        arithmetic_by_id = {constraint.constraint_id: constraint for constraint in arithmetic}
        if any(
            arithmetic_by_id[clue.constraint_ids[0]].source_clue_id != clue.clue_id
            for clue in self.clues
        ):
            raise ValueError("arithmetic source_clue_id values must match their linked clues")

        for given in self.givens:
            if isinstance(given, (AssignmentAtom, ExclusionAtom)):
                if given.variable_id not in variable_ids or given.value_id not in value_ids:
                    raise ValueError("givens must reference variables and values in this puzzle")
            else:
                raise ValueError("Logic Equations givens must be assignments or exclusions")
        return self

    @classmethod
    def _validate_boolean_expression(
        cls,
        expression: BooleanExpression,
        variable_ids: frozenset[VariableId],
    ) -> None:
        if not isinstance(expression, _ALLOWED_BOOLEAN_TYPES):
            raise ValueError(f"unsupported Logic Equations expression: {expression.kind}")
        if isinstance(
            expression,
            (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
        ):
            cls._validate_numeric_expression(expression.left, variable_ids)
            cls._validate_numeric_expression(expression.right, variable_ids)
        elif isinstance(expression, (And, Or)):
            for operand in expression.operands:
                cls._validate_boolean_expression(operand, variable_ids)
        elif isinstance(expression, Not):
            cls._validate_boolean_expression(expression.operand, variable_ids)
        else:
            cls._validate_boolean_expression(expression.premise, variable_ids)
            cls._validate_boolean_expression(expression.conclusion, variable_ids)

    @classmethod
    def _validate_numeric_expression(
        cls,
        expression: NumericExpression,
        variable_ids: frozenset[VariableId],
    ) -> None:
        if isinstance(expression, Constant):
            value = expression.value
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError("Logic Equations constants must be integers")
            return
        if isinstance(expression, VariableReference):
            if expression.variable_id not in variable_ids:
                raise ValueError(
                    f"expression references unknown variable: {expression.variable_id}"
                )
            return
        if isinstance(expression, (Add, Multiply)):
            for operand in expression.operands:
                cls._validate_numeric_expression(operand, variable_ids)
            return
        if isinstance(expression, Subtract):
            cls._validate_numeric_expression(expression.left, variable_ids)
            cls._validate_numeric_expression(expression.right, variable_ids)
            return
        if isinstance(expression, (ExactDivide, Modulo)):
            cls._validate_numeric_expression(expression.dividend, variable_ids)
            cls._validate_numeric_expression(expression.divisor, variable_ids)
            if isinstance(expression.divisor, Constant) and expression.divisor.value == 0:
                raise ValueError("division and modulo divisors cannot be the constant zero")
            return
        cls._validate_numeric_expression(expression.operand, variable_ids)
