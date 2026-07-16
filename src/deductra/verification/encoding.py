"""Shared validation and finite-domain mappings for independent backend encoders."""

from __future__ import annotations

from dataclasses import dataclass

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.constraints import (
    AllDifferentConstraint,
    ArithmeticConstraint,
    Constraint,
    DomainConstraint,
)
from deductra.domain.ids import ValueId, VariableId
from deductra.domain.puzzle import PuzzleSpec
from deductra.reasoning.state import PuzzleState, validate_state
from deductra.verification.contracts import (
    AssignmentNegation,
    ProofObligation,
)


class EncodingError(ValueError):
    """A contract cannot be represented by the bounded CR-004 finite-domain encoder."""


@dataclass(frozen=True, slots=True)
class VariableEncoding:
    """Stable integer mapping for one variable's declared values."""

    variable_id: VariableId
    value_ids: tuple[ValueId, ...]
    numeric_values: tuple[int | None, ...]
    candidate_ids: frozenset[ValueId]

    def code_for(self, value_id: ValueId) -> int:
        try:
            return self.value_ids.index(value_id)
        except ValueError as error:
            raise EncodingError(
                f"value {value_id!r} is outside variable {self.variable_id!r}"
            ) from error

    def value_for(self, code: int) -> ValueId:
        try:
            return self.value_ids[code]
        except IndexError as error:
            raise EncodingError(
                f"backend returned invalid code {code} for {self.variable_id!r}"
            ) from error

    def require_numeric_values(self) -> tuple[int, ...]:
        """Return integer semantics for arithmetic encoders or fail closed."""
        if any(value is None for value in self.numeric_values):
            raise EncodingError(f"variable {self.variable_id!r} has non-integer domain values")
        return tuple(value for value in self.numeric_values if value is not None)


@dataclass(frozen=True, slots=True)
class FiniteDomainProblem:
    """Validated inputs shared as data, never as backend formulas."""

    variables: tuple[VariableEncoding, ...]
    constraints: tuple[Constraint, ...]
    asserted_atoms: tuple[AssignmentAtom | ExclusionAtom, ...]
    assumptions: tuple[AssignmentAtom | ExclusionAtom, ...]
    counter_assumption: AssignmentAtom | ExclusionAtom

    def variable(self, variable_id: VariableId) -> VariableEncoding:
        try:
            return next(item for item in self.variables if item.variable_id == variable_id)
        except StopIteration as error:
            raise EncodingError(f"unknown variable {variable_id!r}") from error


def _require_supported_atom(
    atom: Atom,
    problem_variables: set[VariableId],
) -> AssignmentAtom | ExclusionAtom:
    if not isinstance(atom, (AssignmentAtom, ExclusionAtom)):
        raise EncodingError(f"unsupported atom kind {atom.kind!r}")
    if atom.variable_id not in problem_variables:
        raise EncodingError(f"atom references unknown variable {atom.variable_id!r}")
    return atom


def prepare_problem(
    puzzle: PuzzleSpec,
    state: PuzzleState,
    obligation: ProofObligation,
) -> FiniteDomainProblem:
    """Fail closed unless the puzzle, state, and obligation form one encodable contract."""
    if state.puzzle_revision_id != puzzle.identity.revision_id:
        raise EncodingError("state puzzle revision does not match the specification")
    if obligation.puzzle_revision_id != puzzle.identity.revision_id:
        raise EncodingError("obligation puzzle revision does not match the specification")
    if obligation.source_state_hash != state.state_hash:
        raise EncodingError("obligation source state hash is stale")
    if state.contradiction_ids:
        raise EncodingError("proof obligations cannot use an already contradictory state")
    validation = validate_state(state, puzzle)
    if not validation.valid:
        raise EncodingError(f"source state violates puzzle invariants: {validation.violations}")

    domains = {domain.domain_id: domain for domain in puzzle.domains}
    variables = tuple(
        VariableEncoding(
            variable_id=variable.variable_id,
            value_ids=tuple(value.value_id for value in domains[variable.domain_id].values),
            numeric_values=tuple(
                value.numeric_value
                if isinstance(value.numeric_value, int)
                and not isinstance(value.numeric_value, bool)
                else None
                for value in domains[variable.domain_id].values
            ),
            candidate_ids=state.candidate_domains[variable.variable_id],
        )
        for variable in puzzle.variables
    )
    variable_ids = {item.variable_id for item in variables}
    atoms = tuple(_require_supported_atom(atom, variable_ids) for atom in state.asserted_atoms)
    assumptions = tuple(
        _require_supported_atom(atom, variable_ids) for atom in obligation.assumptions
    )

    if isinstance(obligation.negated_claim, AssignmentNegation):
        counter_assumption: AssignmentAtom | ExclusionAtom = ExclusionAtom(
            variable_id=obligation.negated_claim.variable_id,
            value_id=obligation.negated_claim.value_id,
        )
    else:
        counter_assumption = AssignmentAtom(
            variable_id=obligation.negated_claim.variable_id,
            value_id=obligation.negated_claim.value_id,
        )
    _require_supported_atom(counter_assumption, variable_ids)

    active = state.active_constraint_ids
    constraints = tuple(item for item in puzzle.constraints if item.constraint_id in active)
    if {item.constraint_id for item in constraints} != set(active):
        raise EncodingError("state references constraints absent from the puzzle specification")
    unsupported = tuple(
        item.kind
        for item in constraints
        if not isinstance(
            item,
            (DomainConstraint, AllDifferentConstraint, ArithmeticConstraint),
        )
    )
    if unsupported:
        raise EncodingError(f"unsupported active constraint kinds: {sorted(set(unsupported))}")

    problem = FiniteDomainProblem(
        variables=variables,
        constraints=constraints,
        asserted_atoms=atoms,
        assumptions=assumptions,
        counter_assumption=counter_assumption,
    )
    for atom in (*atoms, *assumptions, counter_assumption):
        variable = problem.variable(atom.variable_id)
        variable.code_for(atom.value_id)
    return problem
