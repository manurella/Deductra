"""Independent CP-SAT table encoding for normalized Logic Grid clues."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from itertools import product
from math import prod

from ortools.sat.python import cp_model

from deductra.domain.constraints import ArithmeticConstraint
from deductra.domain.expressions import (
    And,
    BooleanExpression,
    Cardinality,
    Constant,
    Equal,
    Equivalent,
    GreaterThan,
    GreaterThanOrEqual,
    Implies,
    LessThan,
    LessThanOrEqual,
    Not,
    NotEqual,
    NumericExpression,
    Or,
    Subtract,
    VariableReference,
    Xor,
)
from deductra.domain.ids import VariableId
from deductra.verification.encoding import EncodingError, FiniteDomainProblem

MAX_LOGIC_GRID_TABLE_COMBINATIONS = 1_000_000


def _numeric_variables(expression: NumericExpression) -> frozenset[VariableId]:
    if isinstance(expression, Constant):
        return frozenset()
    if isinstance(expression, VariableReference):
        return frozenset((expression.variable_id,))
    if isinstance(expression, Subtract):
        return _numeric_variables(expression.left) | _numeric_variables(expression.right)
    raise EncodingError(f"unsupported Logic Grid numeric expression: {expression.kind}")


def _boolean_variables(expression: BooleanExpression) -> frozenset[VariableId]:
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        return _numeric_variables(expression.left) | _numeric_variables(expression.right)
    if isinstance(expression, (And, Or, Cardinality)):
        variables: set[VariableId] = set()
        for item in expression.operands:
            variables.update(_boolean_variables(item))
        return frozenset(variables)
    if isinstance(expression, Not):
        return _boolean_variables(expression.operand)
    if isinstance(expression, (Xor, Equivalent)):
        return _boolean_variables(expression.left) | _boolean_variables(expression.right)
    if isinstance(expression, Implies):
        return _boolean_variables(expression.premise) | _boolean_variables(expression.conclusion)
    raise EncodingError(f"unsupported Logic Grid Boolean expression: {expression.kind}")


def _numeric_expression(
    expression: NumericExpression,
    assignments: Mapping[VariableId, int],
    problem: FiniteDomainProblem,
) -> int | Fraction:
    if isinstance(expression, Constant):
        value = expression.value
        if isinstance(value, bool):
            raise EncodingError("Logic Grid constants must be exact numeric values")
        return value
    if isinstance(expression, VariableReference):
        values = problem.variable(expression.variable_id).require_rational_values()
        return values[assignments[expression.variable_id]]
    if isinstance(expression, Subtract):
        return _numeric_expression(expression.left, assignments, problem) - _numeric_expression(
            expression.right, assignments, problem
        )
    raise EncodingError(f"unsupported Logic Grid numeric expression: {expression.kind}")


def _direct_relation(
    expression: BooleanExpression,
    assignments: Mapping[VariableId, int],
) -> bool | None:
    if (
        not isinstance(
            expression,
            (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
        )
        or not isinstance(expression.left, VariableReference)
        or not isinstance(expression.right, VariableReference)
    ):
        return None
    left = assignments[expression.left.variable_id]
    right = assignments[expression.right.variable_id]
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


def _evaluate_boolean(
    expression: BooleanExpression,
    assignments: Mapping[VariableId, int],
    problem: FiniteDomainProblem,
) -> bool:
    direct = _direct_relation(expression, assignments)
    if direct is not None:
        return direct
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        left = _numeric_expression(expression.left, assignments, problem)
        right = _numeric_expression(expression.right, assignments, problem)
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
        return all(_evaluate_boolean(item, assignments, problem) for item in expression.operands)
    if isinstance(expression, Or):
        return any(_evaluate_boolean(item, assignments, problem) for item in expression.operands)
    if isinstance(expression, Not):
        return not _evaluate_boolean(expression.operand, assignments, problem)
    if isinstance(expression, Xor):
        return _evaluate_boolean(expression.left, assignments, problem) != _evaluate_boolean(
            expression.right, assignments, problem
        )
    if isinstance(expression, Implies):
        return not _evaluate_boolean(expression.premise, assignments, problem) or _evaluate_boolean(
            expression.conclusion, assignments, problem
        )
    if isinstance(expression, Equivalent):
        return _evaluate_boolean(expression.left, assignments, problem) == _evaluate_boolean(
            expression.right, assignments, problem
        )
    if isinstance(expression, Cardinality):
        count = sum(_evaluate_boolean(item, assignments, problem) for item in expression.operands)
        return expression.minimum <= count <= expression.maximum
    raise EncodingError(f"unsupported Logic Grid Boolean expression: {expression.kind}")


def add_logic_grid_cpsat_constraint(
    model: cp_model.CpModel,
    constraint: ArithmeticConstraint,
    problem: FiniteDomainProblem,
    variables: dict[str, cp_model.IntVar],
) -> None:
    """Add an exact bounded truth table without importing Z3 semantics."""
    variable_ids = tuple(sorted(_boolean_variables(constraint.expression)))
    code_domains = tuple(
        tuple(
            code
            for code, value_id in enumerate(problem.variable(variable_id).value_ids)
            if value_id in problem.variable(variable_id).candidate_ids
        )
        for variable_id in variable_ids
    )
    combinations = prod(len(domain) for domain in code_domains)
    if combinations > MAX_LOGIC_GRID_TABLE_COMBINATIONS:
        raise EncodingError(
            f"Logic Grid table requires {combinations} combinations; "
            f"limit is {MAX_LOGIC_GRID_TABLE_COMBINATIONS}"
        )
    allowed = tuple(
        codes
        for codes in product(*code_domains)
        if _evaluate_boolean(
            constraint.expression,
            dict(zip(variable_ids, codes, strict=True)),
            problem,
        )
    )
    model.add_allowed_assignments(
        [variables[variable_id] for variable_id in variable_ids],
        allowed,
    )
