"""Symbolic Z3 encoding for Logic Equations arithmetic expressions."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportArgumentType=false, reportReturnType=false

from __future__ import annotations

import z3

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
from deductra.verification.encoding import EncodingError, FiniteDomainProblem


def _variable_numeric_term(
    expression: VariableReference,
    problem: FiniteDomainProblem,
    variables: dict[str, z3.ArithRef],
) -> z3.ArithRef:
    item = problem.variable(expression.variable_id)
    numeric_values = item.require_numeric_values()
    code_variable = variables[expression.variable_id]
    return z3.Sum(
        *(
            z3.If(code_variable == code, numeric_value, 0)
            for code, numeric_value in enumerate(numeric_values)
        )
    )


def _numeric_expression(
    expression: NumericExpression,
    problem: FiniteDomainProblem,
    variables: dict[str, z3.ArithRef],
) -> tuple[z3.ArithRef, z3.BoolRef]:
    if isinstance(expression, Constant):
        value = expression.value
        if not isinstance(value, int) or isinstance(value, bool):
            raise EncodingError("Logic Equations constants must be integers")
        return z3.IntVal(value), z3.BoolVal(True)
    if isinstance(expression, VariableReference):
        return _variable_numeric_term(expression, problem, variables), z3.BoolVal(True)
    if isinstance(expression, Add):
        encoded = tuple(
            _numeric_expression(item, problem, variables) for item in expression.operands
        )
        return z3.Sum(*(item[0] for item in encoded)), z3.And(*(item[1] for item in encoded))
    if isinstance(expression, Multiply):
        encoded = tuple(
            _numeric_expression(item, problem, variables) for item in expression.operands
        )
        product = z3.IntVal(1)
        for term, _valid in encoded:
            product *= term
        return product, z3.And(*(item[1] for item in encoded))
    if isinstance(expression, Subtract):
        left, left_valid = _numeric_expression(expression.left, problem, variables)
        right, right_valid = _numeric_expression(expression.right, problem, variables)
        return left - right, z3.And(left_valid, right_valid)
    if isinstance(expression, (ExactDivide, Modulo)):
        dividend, dividend_valid = _numeric_expression(expression.dividend, problem, variables)
        divisor, divisor_valid = _numeric_expression(expression.divisor, problem, variables)
        nonzero = divisor != 0
        if isinstance(expression, ExactDivide):
            valid = z3.And(
                dividend_valid,
                divisor_valid,
                nonzero,
                dividend % divisor == 0,
            )
            return dividend / divisor, valid
        valid = z3.And(dividend_valid, divisor_valid, divisor > 0)
        return dividend % divisor, valid
    operand, valid = _numeric_expression(expression.operand, problem, variables)
    return -operand, valid


def encode_z3_boolean_expression(
    expression: BooleanExpression,
    problem: FiniteDomainProblem,
    variables: dict[str, z3.ArithRef],
) -> z3.BoolRef:
    """Encode one normalized expression without sharing CP-SAT implementation."""
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        left, left_valid = _numeric_expression(expression.left, problem, variables)
        right, right_valid = _numeric_expression(expression.right, problem, variables)
        if isinstance(expression, Equal):
            relation = left == right
        elif isinstance(expression, NotEqual):
            relation = left != right
        elif isinstance(expression, LessThan):
            relation = left < right
        elif isinstance(expression, LessThanOrEqual):
            relation = left <= right
        elif isinstance(expression, GreaterThan):
            relation = left > right
        else:
            relation = left >= right
        return z3.And(left_valid, right_valid, relation)
    if isinstance(expression, And):
        return z3.And(
            *(
                encode_z3_boolean_expression(item, problem, variables)
                for item in expression.operands
            )
        )
    if isinstance(expression, Or):
        return z3.Or(
            *(
                encode_z3_boolean_expression(item, problem, variables)
                for item in expression.operands
            )
        )
    if isinstance(expression, Not):
        return z3.Not(encode_z3_boolean_expression(expression.operand, problem, variables))
    if isinstance(expression, Implies):
        return z3.Implies(
            encode_z3_boolean_expression(expression.premise, problem, variables),
            encode_z3_boolean_expression(expression.conclusion, problem, variables),
        )
    raise EncodingError(f"unsupported Logic Equations expression: {expression.kind}")
