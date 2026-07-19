"""Symbolic Z3 encoding for normalized Logic Grid clue expressions."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportArgumentType=false, reportReturnType=false

from __future__ import annotations

from fractions import Fraction

import z3

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
from deductra.verification.encoding import EncodingError, FiniteDomainProblem


def _rational(value: int | Fraction) -> z3.ArithRef:
    if isinstance(value, Fraction):
        return z3.RealVal(f"{value.numerator}/{value.denominator}")
    return z3.IntVal(value)


def _variable_numeric_term(
    expression: VariableReference,
    problem: FiniteDomainProblem,
    variables: dict[str, z3.ArithRef],
) -> z3.ArithRef:
    item = problem.variable(expression.variable_id)
    numeric_values = item.require_rational_values()
    code_variable = variables[expression.variable_id]
    return z3.Sum(
        *(
            z3.If(code_variable == code, _rational(value), z3.IntVal(0))
            for code, value in enumerate(numeric_values)
        )
    )


def _numeric_expression(
    expression: NumericExpression,
    problem: FiniteDomainProblem,
    variables: dict[str, z3.ArithRef],
) -> z3.ArithRef:
    if isinstance(expression, Constant):
        value = expression.value
        if isinstance(value, bool):
            raise EncodingError("Logic Grid constants must be exact numeric values")
        return _rational(value)
    if isinstance(expression, VariableReference):
        return _variable_numeric_term(expression, problem, variables)
    if isinstance(expression, Subtract):
        return _numeric_expression(expression.left, problem, variables) - _numeric_expression(
            expression.right, problem, variables
        )
    raise EncodingError(f"unsupported Logic Grid numeric expression: {expression.kind}")


def _direct_relation(
    expression: BooleanExpression,
    variables: dict[str, z3.ArithRef],
) -> z3.BoolRef | None:
    if (
        not isinstance(
            expression,
            (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
        )
        or not isinstance(expression.left, VariableReference)
        or not isinstance(expression.right, VariableReference)
    ):
        return None
    left = variables[expression.left.variable_id]
    right = variables[expression.right.variable_id]
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


def encode_logic_grid_z3_expression(
    expression: BooleanExpression,
    problem: FiniteDomainProblem,
    variables: dict[str, z3.ArithRef],
) -> z3.BoolRef:
    """Encode one Logic Grid clue without sharing CP-SAT evaluation code."""
    direct = _direct_relation(expression, variables)
    if direct is not None:
        return direct
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        left = _numeric_expression(expression.left, problem, variables)
        right = _numeric_expression(expression.right, problem, variables)
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
        return z3.And(
            *(
                encode_logic_grid_z3_expression(item, problem, variables)
                for item in expression.operands
            )
        )
    if isinstance(expression, Or):
        return z3.Or(
            *(
                encode_logic_grid_z3_expression(item, problem, variables)
                for item in expression.operands
            )
        )
    if isinstance(expression, Not):
        return z3.Not(encode_logic_grid_z3_expression(expression.operand, problem, variables))
    if isinstance(expression, Xor):
        return z3.Xor(
            encode_logic_grid_z3_expression(expression.left, problem, variables),
            encode_logic_grid_z3_expression(expression.right, problem, variables),
        )
    if isinstance(expression, Implies):
        return z3.Implies(
            encode_logic_grid_z3_expression(expression.premise, problem, variables),
            encode_logic_grid_z3_expression(expression.conclusion, problem, variables),
        )
    if isinstance(expression, Equivalent):
        return encode_logic_grid_z3_expression(
            expression.left, problem, variables
        ) == encode_logic_grid_z3_expression(expression.right, problem, variables)
    if isinstance(expression, Cardinality):
        count = z3.Sum(
            *(
                z3.If(encode_logic_grid_z3_expression(item, problem, variables), 1, 0)
                for item in expression.operands
            )
        )
        return z3.And(count >= expression.minimum, count <= expression.maximum)
    raise EncodingError(f"unsupported Logic Grid Boolean expression: {expression.kind}")
