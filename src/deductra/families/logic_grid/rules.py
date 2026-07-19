"""Deterministic, non-authoritative human rules for Logic Grid puzzles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from fractions import Fraction

from pydantic import TypeAdapter

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
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
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_json, canonical_sha256
from deductra.families.logic_grid.specification import FAMILY_ID, LogicGridSpec
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


class LogicGridTechnique(StrEnum):
    """Stable v1 technique groups used for explanation and ordering."""

    ASSOCIATION = "association"
    CATEGORY_BIJECTION = "category_bijection"
    ORDERING = "ordering"
    NUMERIC_RELATION = "numeric_relation"
    COMPOUND_LOGIC = "compound_logic"


_TECHNIQUE_RANKS = {
    LogicGridTechnique.ASSOCIATION: 10,
    LogicGridTechnique.CATEGORY_BIJECTION: 20,
    LogicGridTechnique.ORDERING: 30,
    LogicGridTechnique.NUMERIC_RELATION: 40,
    LogicGridTechnique.COMPOUND_LOGIC: 50,
}


def _reference(technique: LogicGridTechnique, title: str) -> RuleReference:
    return RuleReference(
        rule_id=f"deductra:rule:logic-grid:{technique.value}",
        rule_version=RULE_CATALOGUE_VERSION,
        family_scope=(FAMILY_ID,),
        title=title,
        technique_rank=_TECHNIQUE_RANKS[technique],
    )


def _candidate(
    *,
    reference: RuleReference,
    state: PuzzleState,
    conclusion: AssignmentAtom | ExclusionAtom,
    premises: tuple[Atom, ...],
    supporting_constraint: str,
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
    information_gain = (
        len(state.candidate_domains[conclusion.variable_id]) - 1
        if isinstance(conclusion, AssignmentAtom)
        else 1
    )
    return RuleApplicationCandidate(
        candidate_id=f"deductra:candidate:{identity}",
        rule=reference,
        source_state_hash=state.state_hash,
        premises=tuple(sorted(premises, key=canonical_json)),
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
    conclusion = _ATOM_ADAPTER.validate_json(candidate.tie_break_key)
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


def _assignment(variable_id: VariableId, state: PuzzleState) -> AssignmentAtom:
    return AssignmentAtom(
        variable_id=variable_id,
        value_id=next(iter(state.candidate_domains[variable_id])),
    )


def _absence_premise(
    variable_id: VariableId,
    value_id: ValueId,
    state: PuzzleState,
) -> Atom | None:
    exclusion = next(
        (
            atom
            for atom in state.asserted_atoms
            if isinstance(atom, ExclusionAtom)
            and atom.variable_id == variable_id
            and atom.value_id == value_id
        ),
        None,
    )
    if exclusion is not None:
        return exclusion
    return next(
        (
            atom
            for atom in state.asserted_atoms
            if isinstance(atom, AssignmentAtom)
            and atom.variable_id == variable_id
            and atom.value_id != value_id
        ),
        None,
    )


def _numeric_variables(expression: NumericExpression) -> frozenset[VariableId]:
    if isinstance(expression, Constant):
        return frozenset()
    if isinstance(expression, VariableReference):
        return frozenset((expression.variable_id,))
    if isinstance(expression, Subtract):
        return _numeric_variables(expression.left) | _numeric_variables(expression.right)
    raise RuleContractError(f"unsupported Logic Grid numeric expression: {expression.kind}")


def _boolean_variables(expression: BooleanExpression) -> frozenset[VariableId]:
    if isinstance(
        expression,
        (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        return _numeric_variables(expression.left) | _numeric_variables(expression.right)
    if isinstance(expression, (And, Or, Cardinality)):
        variables: set[VariableId] = set()
        for operand in expression.operands:
            variables.update(_boolean_variables(operand))
        return frozenset(variables)
    if isinstance(expression, Not):
        return _boolean_variables(expression.operand)
    if isinstance(expression, (Xor, Equivalent)):
        return _boolean_variables(expression.left) | _boolean_variables(expression.right)
    if isinstance(expression, Implies):
        return _boolean_variables(expression.premise) | _boolean_variables(expression.conclusion)
    raise RuleContractError(f"unsupported Logic Grid Boolean expression: {expression.kind}")


def _technique_for(expression: BooleanExpression) -> LogicGridTechnique:
    if (
        isinstance(expression, (Equal, NotEqual))
        and isinstance(expression.left, VariableReference)
        and isinstance(expression.right, VariableReference)
    ):
        return LogicGridTechnique.ASSOCIATION
    if isinstance(
        expression,
        (LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
    ):
        return LogicGridTechnique.ORDERING
    if isinstance(expression, (Equal, NotEqual)):
        return LogicGridTechnique.NUMERIC_RELATION
    return LogicGridTechnique.COMPOUND_LOGIC


type _Metric = int | Fraction


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


def _evaluate_numeric(
    expression: NumericExpression,
    assignments: Mapping[VariableId, ValueId],
    numeric_values: Mapping[ValueId, _Metric],
) -> _Metric:
    if isinstance(expression, Constant):
        if isinstance(expression.value, bool):
            raise RuleContractError("Logic Grid constants must be exact numeric values")
        return expression.value
    if isinstance(expression, VariableReference):
        value_id = assignments[expression.variable_id]
        try:
            return numeric_values[value_id]
        except KeyError as error:
            raise RuleContractError("Logic Grid numeric expression lacks anchor values") from error
    if isinstance(expression, Subtract):
        return _evaluate_numeric(expression.left, assignments, numeric_values) - _evaluate_numeric(
            expression.right, assignments, numeric_values
        )
    raise RuleContractError(f"unsupported Logic Grid numeric expression: {expression.kind}")


def _evaluate_boolean(
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
            left = _evaluate_numeric(expression.left, assignments, numeric_values)
            right = _evaluate_numeric(expression.right, assignments, numeric_values)
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
            _evaluate_boolean(item, assignments, ordinals, numeric_values)
            for item in expression.operands
        )
    if isinstance(expression, Or):
        return any(
            _evaluate_boolean(item, assignments, ordinals, numeric_values)
            for item in expression.operands
        )
    if isinstance(expression, Not):
        return not _evaluate_boolean(expression.operand, assignments, ordinals, numeric_values)
    if isinstance(expression, Xor):
        return _evaluate_boolean(
            expression.left, assignments, ordinals, numeric_values
        ) != _evaluate_boolean(expression.right, assignments, ordinals, numeric_values)
    if isinstance(expression, Equivalent):
        return _evaluate_boolean(
            expression.left, assignments, ordinals, numeric_values
        ) == _evaluate_boolean(expression.right, assignments, ordinals, numeric_values)
    if isinstance(expression, Implies):
        return not _evaluate_boolean(
            expression.premise, assignments, ordinals, numeric_values
        ) or _evaluate_boolean(expression.conclusion, assignments, ordinals, numeric_values)
    if isinstance(expression, Cardinality):
        true_count = sum(
            _evaluate_boolean(item, assignments, ordinals, numeric_values)
            for item in expression.operands
        )
        return expression.minimum <= true_count <= expression.maximum
    raise RuleContractError(f"unsupported Logic Grid Boolean expression: {expression.kind}")


class AssociationRule:
    """Propagate direct matches and exclusions through candidate intersections."""

    reference = _reference(LogicGridTechnique.ASSOCIATION, "Direct association")

    def find_applications(
        self, puzzle: PuzzleSpec, state: PuzzleState
    ) -> Sequence[RuleApplicationCandidate]:
        if not isinstance(puzzle, LogicGridSpec):
            return ()
        candidates: list[RuleApplicationCandidate] = []
        for constraint in puzzle.constraints:
            if (
                not isinstance(constraint, ArithmeticConstraint)
                or constraint.constraint_id not in state.active_constraint_ids
                or _technique_for(constraint.expression) is not LogicGridTechnique.ASSOCIATION
            ):
                continue
            expression = constraint.expression
            assert isinstance(expression, (Equal, NotEqual))
            assert isinstance(expression.left, VariableReference)
            assert isinstance(expression.right, VariableReference)
            left_id = expression.left.variable_id
            right_id = expression.right.variable_id
            left = state.candidate_domains[left_id]
            right = state.candidate_domains[right_id]
            conclusions: list[tuple[AssignmentAtom | ExclusionAtom, tuple[Atom, ...]]] = []
            if isinstance(expression, Equal):
                intersection = left & right
                for variable_id, domain, other_id in (
                    (left_id, left, right_id),
                    (right_id, right, left_id),
                ):
                    if len(domain) > 1 and len(intersection) == 1:
                        if len(state.candidate_domains[other_id]) == 1:
                            premises: tuple[Atom, ...] = (_assignment(other_id, state),)
                        else:
                            disclosed = tuple(
                                _absence_premise(other_id, value_id, state)
                                for value_id in sorted(domain - intersection)
                            )
                            if any(item is None for item in disclosed):
                                continue
                            premises = tuple(item for item in disclosed if item is not None)
                        conclusions.append(
                            (
                                AssignmentAtom(
                                    variable_id=variable_id,
                                    value_id=next(iter(intersection)),
                                ),
                                premises,
                            )
                        )
                    elif len(intersection) > 1:
                        for value_id in sorted(domain - intersection):
                            premise = _absence_premise(other_id, value_id, state)
                            if premise is not None:
                                conclusions.append(
                                    (
                                        ExclusionAtom(
                                            variable_id=variable_id,
                                            value_id=value_id,
                                        ),
                                        (premise,),
                                    )
                                )
            else:
                for fixed_id, target_id in ((left_id, right_id), (right_id, left_id)):
                    fixed = state.candidate_domains[fixed_id]
                    target = state.candidate_domains[target_id]
                    if len(fixed) == 1 and next(iter(fixed)) in target and len(target) > 1:
                        conclusions.append(
                            (
                                ExclusionAtom(
                                    variable_id=target_id,
                                    value_id=next(iter(fixed)),
                                ),
                                (_assignment(fixed_id, state),),
                            )
                        )
            for conclusion, premises in conclusions:
                candidates.append(
                    _candidate(
                        reference=self.reference,
                        state=state,
                        conclusion=conclusion,
                        premises=premises,
                        supporting_constraint=constraint.constraint_id,
                    )
                )
        return tuple(candidates)

    def apply(self, candidate: RuleApplicationCandidate, state: PuzzleState) -> ProposedDeduction:
        return _proposal(reference=self.reference, candidate=candidate, state=state)


class CategoryBijectionRule:
    """Propagate occupied rows and rows available to only one category item."""

    reference = _reference(LogicGridTechnique.CATEGORY_BIJECTION, "Category bijection")

    def find_applications(
        self, puzzle: PuzzleSpec, state: PuzzleState
    ) -> Sequence[RuleApplicationCandidate]:
        if not isinstance(puzzle, LogicGridSpec):
            return ()
        candidates: list[RuleApplicationCandidate] = []
        for constraint in puzzle.constraints:
            if (
                not isinstance(constraint, AllDifferentConstraint)
                or constraint.constraint_id not in state.active_constraint_ids
            ):
                continue
            for fixed_id in constraint.variable_ids:
                if len(state.candidate_domains[fixed_id]) != 1:
                    continue
                premise = _assignment(fixed_id, state)
                for target_id in constraint.variable_ids:
                    if (
                        target_id != fixed_id
                        and premise.value_id in state.candidate_domains[target_id]
                    ):
                        candidates.append(
                            _candidate(
                                reference=self.reference,
                                state=state,
                                conclusion=ExclusionAtom(
                                    variable_id=target_id, value_id=premise.value_id
                                ),
                                premises=(premise,),
                                supporting_constraint=constraint.constraint_id,
                            )
                        )
            all_values: set[ValueId] = set()
            for variable_id in constraint.variable_ids:
                all_values.update(state.candidate_domains[variable_id])
            for value_id in sorted(all_values):
                supporting = tuple(
                    item
                    for item in constraint.variable_ids
                    if value_id in state.candidate_domains[item]
                )
                if len(supporting) != 1:
                    continue
                target_id = supporting[0]
                if len(state.candidate_domains[target_id]) == 1:
                    continue
                premises: list[Atom] = []
                for other_id in constraint.variable_ids:
                    if other_id == target_id:
                        continue
                    premise = _absence_premise(other_id, value_id, state)
                    if premise is not None:
                        premises.append(premise)
                if len(premises) != len(constraint.variable_ids) - 1:
                    continue
                candidates.append(
                    _candidate(
                        reference=self.reference,
                        state=state,
                        conclusion=AssignmentAtom(variable_id=target_id, value_id=value_id),
                        premises=tuple(premises),
                        supporting_constraint=constraint.constraint_id,
                    )
                )
        return tuple(candidates)

    def apply(self, candidate: RuleApplicationCandidate, state: PuzzleState) -> ProposedDeduction:
        return _proposal(reference=self.reference, candidate=candidate, state=state)


def _ordering_bound_exclusions(
    expression: BooleanExpression,
    state: PuzzleState,
    metrics: Mapping[ValueId, _Metric],
) -> tuple[ExclusionAtom, ...]:
    if (
        not isinstance(expression, (LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual))
        or not isinstance(expression.left, VariableReference)
        or not isinstance(expression.right, VariableReference)
    ):
        return ()
    left_id = expression.left.variable_id
    right_id = expression.right.variable_id
    left = state.candidate_domains[left_id]
    right = state.candidate_domains[right_id]
    if left_id == right_id or len(left) <= 1 or len(right) <= 1:
        return ()
    left_metrics = {item: metrics[item] for item in left}
    right_metrics = {item: metrics[item] for item in right}
    if isinstance(expression, LessThan):
        invalid_left = {
            item for item, value in left_metrics.items() if value >= max(right_metrics.values())
        }
        invalid_right = {
            item for item, value in right_metrics.items() if value <= min(left_metrics.values())
        }
    elif isinstance(expression, LessThanOrEqual):
        invalid_left = {
            item for item, value in left_metrics.items() if value > max(right_metrics.values())
        }
        invalid_right = {
            item for item, value in right_metrics.items() if value < min(left_metrics.values())
        }
    elif isinstance(expression, GreaterThan):
        invalid_left = {
            item for item, value in left_metrics.items() if value <= min(right_metrics.values())
        }
        invalid_right = {
            item for item, value in right_metrics.items() if value >= max(left_metrics.values())
        }
    else:
        invalid_left = {
            item for item, value in left_metrics.items() if value < min(right_metrics.values())
        }
        invalid_right = {
            item for item, value in right_metrics.items() if value > max(left_metrics.values())
        }
    return tuple(
        ExclusionAtom(variable_id=variable_id, value_id=value_id)
        for variable_id, invalid in ((left_id, invalid_left), (right_id, invalid_right))
        for value_id in sorted(invalid)
    )


class ClueCompletionRule:
    """Complete a clue with one unresolved item or disclosed order bounds."""

    def __init__(self, technique: LogicGridTechnique, title: str) -> None:
        if technique in {
            LogicGridTechnique.ASSOCIATION,
            LogicGridTechnique.CATEGORY_BIJECTION,
        }:
            raise ValueError("association and bijection use dedicated rules")
        self.technique = technique
        self.reference = _reference(technique, title)

    def find_applications(
        self, puzzle: PuzzleSpec, state: PuzzleState
    ) -> Sequence[RuleApplicationCandidate]:
        if not isinstance(puzzle, LogicGridSpec):
            return ()
        ordinals, numeric_values = _anchor_semantics(puzzle)
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
                item for item in sorted(variables) if len(state.candidate_domains[item]) > 1
            )
            if len(unresolved) == 2 and self.technique is LogicGridTechnique.ORDERING:
                for conclusion in _ordering_bound_exclusions(
                    constraint.expression, state, ordinals
                ):
                    candidates.append(
                        _candidate(
                            reference=self.reference,
                            state=state,
                            conclusion=conclusion,
                            premises=(),
                            supporting_constraint=constraint.constraint_id,
                        )
                    )
                continue
            if len(unresolved) != 1:
                continue
            variable_id = unresolved[0]
            fixed = variables - {variable_id}
            assignments = {item: next(iter(state.candidate_domains[item])) for item in fixed}
            premises = tuple(_assignment(item, state) for item in sorted(fixed))
            valid: list[ValueId] = []
            invalid: list[ValueId] = []
            for value_id in sorted(state.candidate_domains[variable_id]):
                trial = {**assignments, variable_id: value_id}
                destination = (
                    valid
                    if _evaluate_boolean(
                        constraint.expression,
                        trial,
                        ordinals,
                        numeric_values,
                    )
                    else invalid
                )
                destination.append(value_id)
            if not valid:
                continue
            conclusions: tuple[AssignmentAtom | ExclusionAtom, ...]
            if len(valid) == 1:
                conclusions = (AssignmentAtom(variable_id=variable_id, value_id=valid[0]),)
            else:
                conclusions = tuple(
                    ExclusionAtom(variable_id=variable_id, value_id=item) for item in invalid
                )
            for conclusion in conclusions:
                candidates.append(
                    _candidate(
                        reference=self.reference,
                        state=state,
                        conclusion=conclusion,
                        premises=premises,
                        supporting_constraint=constraint.constraint_id,
                    )
                )
        return tuple(candidates)

    def apply(self, candidate: RuleApplicationCandidate, state: PuzzleState) -> ProposedDeduction:
        return _proposal(reference=self.reference, candidate=candidate, state=state)
