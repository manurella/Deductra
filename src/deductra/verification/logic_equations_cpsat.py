"""Independent CP-SAT table encoding for Logic Equations expressions."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false

from __future__ import annotations

from collections.abc import Mapping
from itertools import product
from math import prod

from ortools.sat.python import cp_model

from deductra.domain.constraints import ArithmeticConstraint
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
from deductra.verification.encoding import EncodingError, FiniteDomainProblem

MAX_TABLE_COMBINATIONS = 1_000_000


def _numeric_variables(expression: NumericExpression) -> frozenset[VariableId]:
    if isinstance(expression, Constant):
        return frozenset[VariableId]()
    if isinstance(expression, VariableReference):
        return frozenset({expression.variable_id})
    if isinstance(expression, (Add, Multiply)):
        variables: set[VariableId] = set()
        for operand in expression.operands:
            variables.update(_numeric_variables(operand))
        return frozenset(variables)
    if isinstance(expression, Subtract):
        return _numeric_variables(expression.left) | _numeric_variables(expression.right)
    if isinstance(expression, (ExactDivide, Modulo)):
        return _numeric_variables(expression.dividend) | _numeric_variables(expression.divisor)
    return _numeric_variables(expression.operand)


def _boolean_variables(expression: BooleanExpression) -> frozenset[VariableId]:
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        return _numeric_variables(expression.left) | _numeric_variables(expression.right)
    if isinstance(expression, (And, Or)):
        variables: set[VariableId] = set()
        for operand in expression.operands:
            variables.update(_boolean_variables(operand))
        return frozenset(variables)
    if isinstance(expression, Not):
        return _boolean_variables(expression.operand)
    if isinstance(expression, Implies):
        return _boolean_variables(expression.premise) | _boolean_variables(expression.conclusion)
    raise EncodingError(f"unsupported Logic Equations expression: {expression.kind}")


class _InvalidArithmetic:
    pass


_INVALID = _InvalidArithmetic()
type _NumericResult = int | _InvalidArithmetic


def _evaluate_numeric(
    expression: NumericExpression,
    assignments: Mapping[VariableId, int],
) -> _NumericResult:
    if isinstance(expression, Constant):
        value = expression.value
        if not isinstance(value, int) or isinstance(value, bool):
            return _INVALID
        return value
    if isinstance(expression, VariableReference):
        return assignments[expression.variable_id]
    if isinstance(expression, Add):
        values = tuple(_evaluate_numeric(item, assignments) for item in expression.operands)
        if any(isinstance(item, _InvalidArithmetic) for item in values):
            return _INVALID
        return sum(item for item in values if isinstance(item, int))
    if isinstance(expression, Multiply):
        result = 1
        for operand in expression.operands:
            value = _evaluate_numeric(operand, assignments)
            if isinstance(value, _InvalidArithmetic):
                return _INVALID
            result *= value
        return result
    if isinstance(expression, Subtract):
        left = _evaluate_numeric(expression.left, assignments)
        right = _evaluate_numeric(expression.right, assignments)
        if isinstance(left, _InvalidArithmetic) or isinstance(right, _InvalidArithmetic):
            return _INVALID
        return left - right
    if isinstance(expression, (ExactDivide, Modulo)):
        dividend = _evaluate_numeric(expression.dividend, assignments)
        divisor = _evaluate_numeric(expression.divisor, assignments)
        if (
            isinstance(dividend, _InvalidArithmetic)
            or isinstance(divisor, _InvalidArithmetic)
            or divisor == 0
        ):
            return _INVALID
        if isinstance(expression, ExactDivide):
            quotient, remainder = divmod(dividend, divisor)
            return quotient if remainder == 0 else _INVALID
        return dividend % divisor if divisor > 0 else _INVALID
    value = _evaluate_numeric(expression.operand, assignments)
    return _INVALID if isinstance(value, _InvalidArithmetic) else -value


def _evaluate_boolean(
    expression: BooleanExpression,
    assignments: Mapping[VariableId, int],
) -> bool:
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        left = _evaluate_numeric(expression.left, assignments)
        right = _evaluate_numeric(expression.right, assignments)
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
        return all(_evaluate_boolean(item, assignments) for item in expression.operands)
    if isinstance(expression, Or):
        return any(_evaluate_boolean(item, assignments) for item in expression.operands)
    if isinstance(expression, Not):
        return not _evaluate_boolean(expression.operand, assignments)
    if isinstance(expression, Implies):
        return not _evaluate_boolean(expression.premise, assignments) or _evaluate_boolean(
            expression.conclusion, assignments
        )
    raise EncodingError(f"unsupported Logic Equations expression: {expression.kind}")


def add_cpsat_arithmetic_constraint(
    model: cp_model.CpModel,
    constraint: ArithmeticConstraint,
    problem: FiniteDomainProblem,
    variables: dict[str, cp_model.IntVar],
) -> None:
    """Add an exact truth table over current candidates, bounded fail-closed."""
    variable_ids = tuple(sorted(_boolean_variables(constraint.expression)))
    if not variable_ids:
        if not _evaluate_boolean(constraint.expression, {}):
            model.add_bool_or([])
        return

    code_domains = tuple(
        tuple(
            code
            for code, value_id in enumerate(problem.variable(variable_id).value_ids)
            if value_id in problem.variable(variable_id).candidate_ids
        )
        for variable_id in variable_ids
    )
    combinations = prod(len(domain) for domain in code_domains)
    if combinations > MAX_TABLE_COMBINATIONS:
        raise EncodingError(
            f"arithmetic table requires {combinations} combinations; "
            f"limit is {MAX_TABLE_COMBINATIONS}"
        )

    numeric_values = {
        variable_id: problem.variable(variable_id).require_numeric_values()
        for variable_id in variable_ids
    }
    allowed: list[tuple[int, ...]] = []
    for codes in product(*code_domains):
        assignment = {
            variable_id: numeric_values[variable_id][code]
            for variable_id, code in zip(variable_ids, codes, strict=True)
        }
        if _evaluate_boolean(constraint.expression, assignment):
            allowed.append(codes)
    model.add_allowed_assignments(
        [variables[variable_id] for variable_id in variable_ids],
        allowed,
    )
