"""Immutable puzzle-state contracts and family-neutral invariant validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import Field, field_serializer, field_validator, model_validator

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.base import DomainModel
from deductra.domain.constraints import AllDifferentConstraint, DomainConstraint
from deductra.domain.ids import (
    BranchId,
    ConstraintId,
    ContradictionId,
    PuzzleRevisionId,
    StateId,
    ValueId,
    VariableId,
)
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_json, canonical_sha256
from deductra.reasoning.events import Sha256Digest

type CandidateDomains = Mapping[VariableId, frozenset[ValueId]]


class PuzzleState(DomainModel):
    """One immutable, hash-addressed projection of a puzzle branch."""

    state_id: StateId
    puzzle_revision_id: PuzzleRevisionId
    sequence_no: Annotated[int, Field(ge=0)]
    branch_id: BranchId
    candidate_domains: CandidateDomains
    asserted_atoms: frozenset[Atom] = frozenset()
    rejected_atoms: frozenset[Atom] = frozenset()
    active_constraint_ids: frozenset[ConstraintId] = frozenset()
    contradiction_ids: tuple[ContradictionId, ...] = ()
    solved: bool
    state_hash: Sha256Digest

    @field_validator("candidate_domains", mode="after")
    @classmethod
    def freeze_candidate_domains(cls, value: CandidateDomains) -> CandidateDomains:
        normalized = {
            variable_id: frozenset(value_ids) for variable_id, value_ids in sorted(value.items())
        }
        return MappingProxyType(normalized)

    @field_serializer("candidate_domains")
    def serialize_candidate_domains(self, value: CandidateDomains) -> dict[str, list[str]]:
        return {variable_id: sorted(value_ids) for variable_id, value_ids in sorted(value.items())}

    @field_serializer("asserted_atoms", "rejected_atoms")
    def serialize_atoms(self, value: frozenset[Atom]) -> list[dict[str, Any]]:
        return [atom.model_dump(mode="json") for atom in sorted(value, key=canonical_json)]

    @field_serializer("active_constraint_ids")
    def serialize_constraint_ids(self, value: frozenset[ConstraintId]) -> list[str]:
        return sorted(value)

    @model_validator(mode="after")
    def validate_structural_invariants(self) -> PuzzleState:
        if not self.candidate_domains:
            raise ValueError("candidate_domains must contain at least one variable")
        if (
            any(not values for values in self.candidate_domains.values())
            and not self.contradiction_ids
        ):
            raise ValueError("empty candidate domains require an explicit contradiction")
        if self.asserted_atoms & self.rejected_atoms:
            raise ValueError("asserted and rejected atoms must not overlap")
        if len(self.contradiction_ids) != len(set(self.contradiction_ids)):
            raise ValueError("contradiction identifiers must be unique")

        assignments = {
            (atom.variable_id, atom.value_id)
            for atom in self.asserted_atoms
            if isinstance(atom, AssignmentAtom)
        }
        for variable_id, values in self.candidate_domains.items():
            if len(values) == 1 and (variable_id, next(iter(values))) not in assignments:
                raise ValueError("singleton candidate domains require an assignment projection")

        expected_solved = not self.contradiction_ids and all(
            len(values) == 1 for values in self.candidate_domains.values()
        )
        if self.solved != expected_solved:
            raise ValueError("solved must match the candidate and contradiction projection")
        if self.state_hash != compute_state_hash(self):
            raise ValueError("state_hash does not match the canonical state")
        return self


@dataclass(frozen=True, slots=True)
class StateValidation:
    """Result of validating a state against its immutable puzzle specification."""

    violations: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.violations


def compute_state_hash(state: PuzzleState) -> str:
    """Hash every canonical state field except the digest itself."""
    return canonical_sha256(state.model_dump(mode="json", exclude={"state_hash"}))


def build_state(
    *,
    state_id: StateId,
    puzzle_revision_id: PuzzleRevisionId,
    sequence_no: int,
    branch_id: BranchId,
    candidate_domains: CandidateDomains,
    asserted_atoms: frozenset[Atom],
    rejected_atoms: frozenset[Atom],
    active_constraint_ids: frozenset[ConstraintId],
    contradiction_ids: tuple[ContradictionId, ...],
) -> PuzzleState:
    normalized_domains = MappingProxyType(
        {
            variable_id: frozenset(value_ids)
            for variable_id, value_ids in sorted(candidate_domains.items())
        }
    )
    solved = not contradiction_ids and all(
        len(values) == 1 for values in normalized_domains.values()
    )
    unsigned = PuzzleState.model_construct(
        state_id=state_id,
        puzzle_revision_id=puzzle_revision_id,
        sequence_no=sequence_no,
        branch_id=branch_id,
        candidate_domains=normalized_domains,
        asserted_atoms=asserted_atoms,
        rejected_atoms=rejected_atoms,
        active_constraint_ids=active_constraint_ids,
        contradiction_ids=contradiction_ids,
        solved=solved,
        state_hash="0" * 64,
    )
    return PuzzleState(
        state_id=state_id,
        puzzle_revision_id=puzzle_revision_id,
        sequence_no=sequence_no,
        branch_id=branch_id,
        candidate_domains=normalized_domains,
        asserted_atoms=asserted_atoms,
        rejected_atoms=rejected_atoms,
        active_constraint_ids=active_constraint_ids,
        contradiction_ids=contradiction_ids,
        solved=solved,
        state_hash=compute_state_hash(unsigned),
    )


def create_initial_state(
    puzzle: PuzzleSpec,
    *,
    state_id: StateId,
    branch_id: BranchId,
    sequence_no: int,
) -> PuzzleState:
    """Create the deterministic genesis projection for one puzzle revision."""
    domains = {domain.domain_id: domain for domain in puzzle.domains}
    candidates: dict[VariableId, set[ValueId]] = {
        variable.variable_id: {value.value_id for value in domains[variable.domain_id].values}
        for variable in puzzle.variables
    }
    for constraint in puzzle.constraints:
        if isinstance(constraint, DomainConstraint):
            if constraint.variable_id not in candidates:
                raise ValueError("domain constraint references an unknown variable")
            candidates[constraint.variable_id].intersection_update(constraint.allowed_value_ids)

    asserted: set[Atom] = set(puzzle.givens)
    for atom in puzzle.givens:
        if isinstance(atom, AssignmentAtom):
            if (
                atom.variable_id not in candidates
                or atom.value_id not in candidates[atom.variable_id]
            ):
                raise ValueError("assignment given is outside the variable domain")
            candidates[atom.variable_id] = {atom.value_id}
        elif isinstance(atom, ExclusionAtom):
            if (
                atom.variable_id not in candidates
                or atom.value_id not in candidates[atom.variable_id]
            ):
                raise ValueError("exclusion given is outside the variable domain")
            candidates[atom.variable_id].remove(atom.value_id)

    for variable_id, value_ids in candidates.items():
        if len(value_ids) == 1:
            asserted.add(AssignmentAtom(variable_id=variable_id, value_id=next(iter(value_ids))))

    state = build_state(
        state_id=state_id,
        puzzle_revision_id=puzzle.identity.revision_id,
        sequence_no=sequence_no,
        branch_id=branch_id,
        candidate_domains={key: frozenset(value) for key, value in candidates.items()},
        asserted_atoms=frozenset(asserted),
        rejected_atoms=frozenset(),
        active_constraint_ids=frozenset(item.constraint_id for item in puzzle.constraints),
        contradiction_ids=(),
    )
    validation = validate_state(state, puzzle)
    if not validation.valid:
        raise ValueError(f"initial state violates puzzle invariants: {validation.violations}")
    return state


def validate_state(state: PuzzleState, puzzle: PuzzleSpec) -> StateValidation:
    """Check cross-contract state invariants without solving the puzzle."""
    violations: list[str] = []
    if state.puzzle_revision_id != puzzle.identity.revision_id:
        violations.append("puzzle_revision_mismatch")

    domains = {domain.domain_id: domain for domain in puzzle.domains}
    variable_domains = {
        variable.variable_id: {value.value_id for value in domains[variable.domain_id].values}
        for variable in puzzle.variables
    }
    if set(state.candidate_domains) != set(variable_domains):
        violations.append("candidate_variable_mismatch")
    for variable_id, candidates in state.candidate_domains.items():
        if variable_id in variable_domains and not candidates <= variable_domains[variable_id]:
            violations.append(f"candidate_outside_domain:{variable_id}")

    assignments: dict[VariableId, ValueId] = {}
    for atom in state.asserted_atoms:
        if isinstance(atom, AssignmentAtom):
            if (
                atom.variable_id not in variable_domains
                or atom.value_id not in variable_domains[atom.variable_id]
            ):
                violations.append(f"assignment_outside_domain:{atom.variable_id}")
            previous = assignments.setdefault(atom.variable_id, atom.value_id)
            if previous != atom.value_id:
                violations.append(f"conflicting_assignment:{atom.variable_id}")
            if state.candidate_domains.get(atom.variable_id) != frozenset({atom.value_id}):
                violations.append(f"assignment_candidate_mismatch:{atom.variable_id}")
        elif isinstance(atom, ExclusionAtom):
            if atom.value_id in state.candidate_domains.get(atom.variable_id, frozenset()):
                violations.append(f"excluded_candidate_present:{atom.variable_id}")

    known_constraints = {constraint.constraint_id for constraint in puzzle.constraints}
    if not state.active_constraint_ids <= known_constraints:
        violations.append("unknown_active_constraint")
    for constraint in puzzle.constraints:
        if isinstance(constraint, AllDifferentConstraint):
            assigned = [
                assignments[item] for item in constraint.variable_ids if item in assignments
            ]
            if len(assigned) != len(set(assigned)):
                violations.append(f"all_different_violation:{constraint.constraint_id}")

    return StateValidation(tuple(dict.fromkeys(violations)))
