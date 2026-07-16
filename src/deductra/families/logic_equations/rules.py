"""Deterministic, non-authoritative human rules for Logic Equations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

from pydantic import TypeAdapter

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
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
    Negate,
    Not,
    NotEqual,
    NumericExpression,
    Or,
    Subtract,
    VariableReference,
)
from deductra.domain.ids import ValueId, VariableId
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_json, canonical_sha256
from deductra.families.logic_equations.specification import (
    FAMILY_ID,
    LogicEquationsSpec,
)
from deductra.reasoning.rules import (
    ProposedDeduction,
    RuleApplicationCandidate,
    RuleContractError,
    RuleReference,
)
from deductra.reasoning.state import PuzzleState

RULE_CATALOGUE_VERSION = "1.0.0"

_ATOM_ADAPTER: TypeAdapter[AssignmentAtom | ExclusionAtom] = TypeAdapter(
    AssignmentAtom | ExclusionAtom
)


class LogicEquationsTechnique(StrEnum):
    """Stable v1 technique groups used for explanation and ordering."""

    DIRECT_RELATION = "direct_relation"
    ALL_DIFFERENT = "all_different"
    ARITHMETIC = "arithmetic"
    PARITY_DIVISIBILITY = "parity_divisibility"
    DISJUNCTION = "disjunction"
    IMPLICATION = "implication"


_TECHNIQUE_RANKS = {
    LogicEquationsTechnique.DIRECT_RELATION: 10,
    LogicEquationsTechnique.ALL_DIFFERENT: 20,
    LogicEquationsTechnique.ARITHMETIC: 30,
    LogicEquationsTechnique.PARITY_DIVISIBILITY: 35,
    LogicEquationsTechnique.DISJUNCTION: 40,
    LogicEquationsTechnique.IMPLICATION: 45,
}


def _reference(technique: LogicEquationsTechnique, title: str) -> RuleReference:
    return RuleReference(
        rule_id=f"deductra:rule:logic-equations:{technique.value}",
        rule_version=RULE_CATALOGUE_VERSION,
        family_scope=(FAMILY_ID,),
        title=title,
        technique_rank=_TECHNIQUE_RANKS[technique],
    )


def _conclusion(candidate: RuleApplicationCandidate) -> AssignmentAtom | ExclusionAtom:
    return _ATOM_ADAPTER.validate_json(candidate.tie_break_key)


def _candidate(
    *,
    reference: RuleReference,
    state: PuzzleState,
    conclusion: AssignmentAtom | ExclusionAtom,
    premises: tuple[Atom, ...],
    supporting_constraint: str,
    information_gain: int,
) -> RuleApplicationCandidate:
    tie_break_key = canonical_json(conclusion)
    identity = canonical_sha256(
        {
            "conclusion": conclusion,
            "rule": reference,
            "source_state_hash": state.state_hash,
            "supporting_constraint": supporting_constraint,
        }
    )
    return RuleApplicationCandidate(
        candidate_id=f"deductra:candidate:{identity}",
        rule=reference,
        source_state_hash=state.state_hash,
        premises=premises,
        affected_variables=(conclusion.variable_id,),
        supporting_constraints=(supporting_constraint,),
        information_gain=information_gain,
        pedagogical_cost=reference.technique_rank,
        tie_break_key=tie_break_key,
    )


def _proposal(
    *,
    reference: RuleReference,
    candidate: RuleApplicationCandidate,
    state: PuzzleState,
) -> ProposedDeduction:
    if candidate.rule != reference:
        raise RuleContractError("candidate rule reference does not match this rule")
    if candidate.source_state_hash != state.state_hash:
        raise RuleContractError("candidate source state is stale")
    conclusion = _conclusion(candidate)
    return ProposedDeduction(
        candidate_id=candidate.candidate_id,
        source_state_hash=candidate.source_state_hash,
        rule=reference,
        premises=candidate.premises,
        conclusions=(conclusion,),
        affected_variables=candidate.affected_variables,
        supporting_constraints=candidate.supporting_constraints,
        explanation_parameters={
            "technique": reference.rule_id.rsplit(":", 1)[1],
            "variable_id": conclusion.variable_id,
            "value_id": conclusion.value_id,
        },
    )


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
    raise RuleContractError(f"unsupported Logic Equations expression: {expression.kind}")


class _InvalidArithmetic:
    pass


_INVALID = _InvalidArithmetic()
type _NumericResult = int | _InvalidArithmetic


def _evaluate_numeric(
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
        return dividend % divisor
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
    raise RuleContractError(f"unsupported Logic Equations expression: {expression.kind}")


def _contains_modulo(expression: NumericExpression | BooleanExpression) -> bool:
    if isinstance(expression, Modulo):
        return True
    if isinstance(expression, (Constant, VariableReference)):
        return False
    if isinstance(expression, (Add, Multiply)):
        return any(_contains_modulo(item) for item in expression.operands)
    if isinstance(expression, Subtract):
        return _contains_modulo(expression.left) or _contains_modulo(expression.right)
    if isinstance(expression, ExactDivide):
        return _contains_modulo(expression.dividend) or _contains_modulo(expression.divisor)
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        return _contains_modulo(expression.left) or _contains_modulo(expression.right)
    if isinstance(expression, (And, Or)):
        return any(_contains_modulo(item) for item in expression.operands)
    if isinstance(expression, Not):
        return _contains_modulo(expression.operand)
    if isinstance(expression, Implies):
        return _contains_modulo(expression.premise) or _contains_modulo(expression.conclusion)
    if isinstance(expression, Negate):
        return _contains_modulo(expression.operand)
    return False


def _is_direct_relation(expression: BooleanExpression) -> bool:
    if not isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        return False
    simple = (Constant, VariableReference)
    return isinstance(expression.left, simple) and isinstance(expression.right, simple)


def _technique_for(expression: BooleanExpression) -> LogicEquationsTechnique:
    if isinstance(expression, Implies):
        return LogicEquationsTechnique.IMPLICATION
    if isinstance(expression, Or):
        return LogicEquationsTechnique.DISJUNCTION
    if _contains_modulo(expression):
        return LogicEquationsTechnique.PARITY_DIVISIBILITY
    if _is_direct_relation(expression):
        return LogicEquationsTechnique.DIRECT_RELATION
    return LogicEquationsTechnique.ARITHMETIC


def _numeric_value_map(puzzle: LogicEquationsSpec) -> dict[ValueId, int]:
    result: dict[ValueId, int] = {}
    for value in puzzle.domains[0].values:
        numeric_value = value.numeric_value
        if not isinstance(numeric_value, int) or isinstance(numeric_value, bool):
            raise RuleContractError("Logic Equations values must be integers")
        result[value.value_id] = numeric_value
    return result


class ConstraintPropagationRule:
    """Resolve one variable from one fully grounded arithmetic constraint."""

    def __init__(self, technique: LogicEquationsTechnique, title: str) -> None:
        if technique is LogicEquationsTechnique.ALL_DIFFERENT:
            raise ValueError("all-different propagation uses its dedicated rule")
        self.technique = technique
        self.reference = _reference(technique, title)

    def find_applications(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
    ) -> Sequence[RuleApplicationCandidate]:
        if not isinstance(puzzle, LogicEquationsSpec):
            return ()
        numeric_values = _numeric_value_map(puzzle)
        candidates: list[RuleApplicationCandidate] = []
        for constraint in puzzle.constraints:
            if (
                not isinstance(constraint, ArithmeticConstraint)
                or constraint.constraint_id not in state.active_constraint_ids
                or _technique_for(constraint.expression) is not self.technique
            ):
                continue
            variables = _boolean_variables(constraint.expression)
            unresolved = tuple(
                variable_id
                for variable_id in sorted(variables)
                if len(state.candidate_domains[variable_id]) > 1
            )
            if len(unresolved) != 1:
                continue
            variable_id = unresolved[0]
            fixed = variables - {variable_id}
            assignments = {
                item: numeric_values[next(iter(state.candidate_domains[item]))] for item in fixed
            }
            premises = tuple(
                AssignmentAtom(
                    variable_id=item,
                    value_id=next(iter(state.candidate_domains[item])),
                )
                for item in sorted(fixed)
            )
            valid: list[ValueId] = []
            invalid: list[ValueId] = []
            for value_id in sorted(state.candidate_domains[variable_id]):
                trial = {**assignments, variable_id: numeric_values[value_id]}
                destination = valid if _evaluate_boolean(constraint.expression, trial) else invalid
                destination.append(value_id)
            if not valid:
                continue
            conclusions: tuple[AssignmentAtom | ExclusionAtom, ...]
            if len(valid) == 1:
                conclusions = (AssignmentAtom(variable_id=variable_id, value_id=valid[0]),)
            else:
                conclusions = tuple(
                    ExclusionAtom(variable_id=variable_id, value_id=value_id)
                    for value_id in invalid
                )
            for conclusion in conclusions:
                information_gain = (
                    len(state.candidate_domains[variable_id]) - 1
                    if isinstance(conclusion, AssignmentAtom)
                    else 1
                )
                candidates.append(
                    _candidate(
                        reference=self.reference,
                        state=state,
                        conclusion=conclusion,
                        premises=premises,
                        supporting_constraint=constraint.constraint_id,
                        information_gain=information_gain,
                    )
                )
        return tuple(candidates)

    def apply(
        self,
        candidate: RuleApplicationCandidate,
        state: PuzzleState,
    ) -> ProposedDeduction:
        return _proposal(reference=self.reference, candidate=candidate, state=state)


class AllDifferentPropagationRule:
    """Eliminate values already assigned inside the all-different scope."""

    reference = _reference(
        LogicEquationsTechnique.ALL_DIFFERENT,
        "All-different propagation",
    )

    def find_applications(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
    ) -> Sequence[RuleApplicationCandidate]:
        if not isinstance(puzzle, LogicEquationsSpec):
            return ()
        candidates: list[RuleApplicationCandidate] = []
        for constraint in puzzle.constraints:
            if (
                not isinstance(constraint, AllDifferentConstraint)
                or constraint.constraint_id not in state.active_constraint_ids
            ):
                continue
            assigned = tuple(
                AssignmentAtom(
                    variable_id=variable_id,
                    value_id=next(iter(state.candidate_domains[variable_id])),
                )
                for variable_id in constraint.variable_ids
                if len(state.candidate_domains[variable_id]) == 1
            )
            for premise in assigned:
                for variable_id in constraint.variable_ids:
                    domain = state.candidate_domains[variable_id]
                    if variable_id == premise.variable_id or premise.value_id not in domain:
                        continue
                    conclusion = ExclusionAtom(
                        variable_id=variable_id,
                        value_id=premise.value_id,
                    )
                    candidates.append(
                        _candidate(
                            reference=self.reference,
                            state=state,
                            conclusion=conclusion,
                            premises=(premise,),
                            supporting_constraint=constraint.constraint_id,
                            information_gain=1,
                        )
                    )
        return tuple(candidates)

    def apply(
        self,
        candidate: RuleApplicationCandidate,
        state: PuzzleState,
    ) -> ProposedDeduction:
        return _proposal(reference=self.reference, candidate=candidate, state=state)
