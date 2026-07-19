"""Independent final-solution checker for Logic Grid puzzles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.base import DomainModel
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
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
from deductra.domain.ids import ValueId, VariableId
from deductra.families.logic_grid.specification import LogicGridSpec

type _Metric = int | Fraction


class LogicGridSolutionCheck(DomainModel):
    """Deterministic acceptance result for one complete row assignment."""

    accepted: bool
    violations: tuple[str, ...] = ()


def _anchor_semantics(
    puzzle: LogicGridSpec,
) -> tuple[dict[ValueId, int], dict[ValueId, _Metric]]:
    category = next(
        item for item in puzzle.categories if item.category_id == puzzle.anchor_category_id
    )
    domain = next(item for item in puzzle.domains if item.domain_id == category.domain_id)
    ordinals: dict[ValueId, int] = {}
    numeric_values: dict[ValueId, _Metric] = {}
    for index, value in enumerate(domain.values, start=1):
        ordinals[value.value_id] = value.ordinal if value.ordinal is not None else index
        if value.numeric_value is not None:
            numeric_values[value.value_id] = value.numeric_value
    return ordinals, numeric_values


def _numeric(
    expression: NumericExpression,
    assignments: Mapping[VariableId, ValueId],
    numeric_values: Mapping[ValueId, _Metric],
) -> _Metric:
    if isinstance(expression, Constant):
        if isinstance(expression.value, bool):
            raise ValueError("Logic Grid constants must be exact numeric values")
        return expression.value
    if isinstance(expression, VariableReference):
        try:
            return numeric_values[assignments[expression.variable_id]]
        except KeyError as error:
            raise ValueError("Logic Grid numeric expression lacks anchor values") from error
    if isinstance(expression, Subtract):
        return _numeric(expression.left, assignments, numeric_values) - _numeric(
            expression.right, assignments, numeric_values
        )
    raise ValueError(f"unsupported Logic Grid numeric expression: {expression.kind}")


def _boolean(
    expression: BooleanExpression,
    assignments: Mapping[VariableId, ValueId],
    ordinals: Mapping[ValueId, int],
    numeric_values: Mapping[ValueId, _Metric],
) -> bool:
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        if isinstance(expression.left, VariableReference) and isinstance(
            expression.right, VariableReference
        ):
            left_value_id = assignments[expression.left.variable_id]
            right_value_id = assignments[expression.right.variable_id]
            if isinstance(expression, Equal):
                return left_value_id == right_value_id
            if isinstance(expression, NotEqual):
                return left_value_id != right_value_id
            left: _Metric = ordinals[left_value_id]
            right: _Metric = ordinals[right_value_id]
        else:
            left = _numeric(expression.left, assignments, numeric_values)
            right = _numeric(expression.right, assignments, numeric_values)
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
        return all(
            _boolean(item, assignments, ordinals, numeric_values) for item in expression.operands
        )
    if isinstance(expression, Or):
        return any(
            _boolean(item, assignments, ordinals, numeric_values) for item in expression.operands
        )
    if isinstance(expression, Not):
        return not _boolean(expression.operand, assignments, ordinals, numeric_values)
    if isinstance(expression, Xor):
        return _boolean(expression.left, assignments, ordinals, numeric_values) != _boolean(
            expression.right, assignments, ordinals, numeric_values
        )
    if isinstance(expression, Equivalent):
        return _boolean(expression.left, assignments, ordinals, numeric_values) == _boolean(
            expression.right, assignments, ordinals, numeric_values
        )
    if isinstance(expression, Implies):
        return not _boolean(expression.premise, assignments, ordinals, numeric_values) or _boolean(
            expression.conclusion, assignments, ordinals, numeric_values
        )
    if isinstance(expression, Cardinality):
        true_count = sum(
            _boolean(item, assignments, ordinals, numeric_values) for item in expression.operands
        )
        return expression.minimum <= true_count <= expression.maximum
    raise ValueError(f"unsupported Logic Grid Boolean expression: {expression.kind}")


def check_logic_grid_solution(
    puzzle: LogicGridSpec,
    assignments: Sequence[AssignmentAtom],
) -> LogicGridSolutionCheck:
    """Check completeness, row domains, givens, bijections, and every clue."""
    violations: list[str] = []
    variables = {variable.variable_id: variable for variable in puzzle.variables}
    anchor_category = next(
        category
        for category in puzzle.categories
        if category.category_id == puzzle.anchor_category_id
    )
    anchor_domain = next(
        domain for domain in puzzle.domains if domain.domain_id == anchor_category.domain_id
    )
    value_ids = {value.value_id for value in anchor_domain.values}
    by_variable: dict[VariableId, ValueId] = {}

    for assignment in assignments:
        if assignment.variable_id not in variables:
            violations.append(f"unknown_variable:{assignment.variable_id}")
            continue
        if assignment.variable_id in by_variable:
            violations.append(f"duplicate_assignment:{assignment.variable_id}")
            continue
        if assignment.value_id not in value_ids:
            violations.append(f"unknown_value:{assignment.value_id}")
            continue
        by_variable[assignment.variable_id] = assignment.value_id

    for variable_id in sorted(set(variables) - set(by_variable)):
        violations.append(f"missing_assignment:{variable_id}")
    if violations:
        return LogicGridSolutionCheck(
            accepted=False,
            violations=tuple(dict.fromkeys(violations)),
        )

    for given in puzzle.givens:
        if isinstance(given, AssignmentAtom):
            failed = by_variable[given.variable_id] != given.value_id
        elif isinstance(given, ExclusionAtom):
            failed = by_variable[given.variable_id] == given.value_id
        else:
            raise ValueError("Logic Grid givens must be assignments or exclusions")
        if failed:
            violations.append(f"given_failed:{given.kind}:{given.variable_id}")

    ordinals, numeric_values = _anchor_semantics(puzzle)
    for constraint in puzzle.constraints:
        if isinstance(constraint, AllDifferentConstraint):
            selected = tuple(by_variable[item] for item in constraint.variable_ids)
            if len(selected) != len(set(selected)):
                violations.append(f"constraint_failed:{constraint.constraint_id}")
        elif isinstance(constraint, ArithmeticConstraint) and not _boolean(
            constraint.expression,
            by_variable,
            ordinals,
            numeric_values,
        ):
            violations.append(f"constraint_failed:{constraint.constraint_id}")

    normalized = tuple(dict.fromkeys(violations))
    return LogicGridSolutionCheck(accepted=not normalized, violations=normalized)
