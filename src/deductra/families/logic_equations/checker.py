"""Independent final-solution checker for Logic Equations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from deductra.domain.atoms import AssignmentAtom
from deductra.domain.base import DomainModel
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
from deductra.domain.ids import ValueId, VariableId
from deductra.families.logic_equations.specification import LogicEquationsSpec


class LogicEquationsSolutionCheck(DomainModel):
    """Deterministic acceptance result for one complete assignment."""

    accepted: bool
    violations: tuple[str, ...] = ()


class _InvalidArithmetic:
    pass


_INVALID = _InvalidArithmetic()
type _NumericResult = int | _InvalidArithmetic


def _numeric(
    expression: NumericExpression,
    assignments: Mapping[VariableId, int],
) -> _NumericResult:
    if isinstance(expression, Constant):
        return (
            expression.value
            if isinstance(expression.value, int) and not isinstance(expression.value, bool)
            else _INVALID
        )
    if isinstance(expression, VariableReference):
        return assignments[expression.variable_id]
    if isinstance(expression, Add):
        values = tuple(_numeric(item, assignments) for item in expression.operands)
        if any(isinstance(item, _InvalidArithmetic) for item in values):
            return _INVALID
        return sum(item for item in values if isinstance(item, int))
    if isinstance(expression, Multiply):
        result = 1
        for operand in expression.operands:
            value = _numeric(operand, assignments)
            if isinstance(value, _InvalidArithmetic):
                return _INVALID
            result *= value
        return result
    if isinstance(expression, Subtract):
        left = _numeric(expression.left, assignments)
        right = _numeric(expression.right, assignments)
        if isinstance(left, _InvalidArithmetic) or isinstance(right, _InvalidArithmetic):
            return _INVALID
        return left - right
    if isinstance(expression, (ExactDivide, Modulo)):
        dividend = _numeric(expression.dividend, assignments)
        divisor = _numeric(expression.divisor, assignments)
        if (
            isinstance(dividend, _InvalidArithmetic)
            or isinstance(divisor, _InvalidArithmetic)
            or divisor == 0
        ):
            return _INVALID
        if isinstance(expression, ExactDivide):
            quotient, remainder = divmod(dividend, divisor)
            return quotient if remainder == 0 else _INVALID
        return dividend % divisor
    value = _numeric(expression.operand, assignments)
    return _INVALID if isinstance(value, _InvalidArithmetic) else -value


def _boolean(
    expression: BooleanExpression,
    assignments: Mapping[VariableId, int],
) -> bool:
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        left = _numeric(expression.left, assignments)
        right = _numeric(expression.right, assignments)
        if isinstance(left, _InvalidArithmetic) or isinstance(right, _InvalidArithmetic):
            return False
        if isinstance(expression, Equal):
            return left == right
        if isinstance(expression, NotEqual):
            return left != right
        if isinstance(expression, LessThan):
            return left < right
        if isinstance(expression, LessThanOrEqual):
            return left <= right
        if isinstance(expression, GreaterThan):
            return left > right
        return left >= right
    if isinstance(expression, And):
        return all(_boolean(item, assignments) for item in expression.operands)
    if isinstance(expression, Or):
        return any(_boolean(item, assignments) for item in expression.operands)
    if isinstance(expression, Not):
        return not _boolean(expression.operand, assignments)
    if isinstance(expression, Implies):
        return not _boolean(expression.premise, assignments) or _boolean(
            expression.conclusion, assignments
        )
    return False


def check_logic_equations_solution(
    puzzle: LogicEquationsSpec,
    assignments: Sequence[AssignmentAtom],
) -> LogicEquationsSolutionCheck:
    """Check completeness, domains, all-different, and every arithmetic clue."""
    violations: list[str] = []
    variables = {variable.variable_id: variable for variable in puzzle.variables}
    domain = puzzle.domains[0]
    values = {value.value_id: value for value in domain.values}
    by_variable: dict[VariableId, ValueId] = {}

    for assignment in assignments:
        if assignment.variable_id not in variables:
            violations.append(f"unknown_variable:{assignment.variable_id}")
            continue
        if assignment.variable_id in by_variable:
            violations.append(f"duplicate_assignment:{assignment.variable_id}")
            continue
        if assignment.value_id not in values:
            violations.append(f"unknown_value:{assignment.value_id}")
            continue
        by_variable[assignment.variable_id] = assignment.value_id

    for variable_id in sorted(set(variables) - set(by_variable)):
        violations.append(f"missing_assignment:{variable_id}")

    if violations:
        normalized = tuple(dict.fromkeys(violations))
        return LogicEquationsSolutionCheck(accepted=False, violations=normalized)

    numeric_assignments: dict[VariableId, int] = {}
    for variable_id, value_id in by_variable.items():
        numeric_value = values[value_id].numeric_value
        if not isinstance(numeric_value, int) or isinstance(numeric_value, bool):
            raise ValueError("Logic Equations values must be integers")
        numeric_assignments[variable_id] = numeric_value
    for constraint in puzzle.constraints:
        if isinstance(constraint, AllDifferentConstraint):
            selected = tuple(by_variable[variable_id] for variable_id in constraint.variable_ids)
            if len(selected) != len(set(selected)):
                violations.append(f"constraint_failed:{constraint.constraint_id}")
        elif isinstance(constraint, ArithmeticConstraint) and not _boolean(
            constraint.expression, numeric_assignments
        ):
            violations.append(f"constraint_failed:{constraint.constraint_id}")

    normalized = tuple(dict.fromkeys(violations))
    return LogicEquationsSolutionCheck(
        accepted=not normalized,
        violations=normalized,
    )
