"""Top-level immutable puzzle specification."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import model_validator

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.base import MetadataModel
from deductra.domain.constraints import CompositeConstraint, Constraint
from deductra.domain.ids import (
    ClueId,
    ConstraintId,
    GenerationId,
    ProvenanceId,
    PuzzleId,
    PuzzleRevisionId,
)
from deductra.domain.values import Domain, Variable


class PuzzleIdentity(MetadataModel):
    """Versioned identity and authorship for one immutable puzzle revision."""

    puzzle_id: PuzzleId
    revision_id: PuzzleRevisionId
    family_id: str
    schema_version: str
    title: str
    author: str | None = None
    source_kind: Literal["golden", "generated", "user", "imported"]
    parent_revision_id: PuzzleRevisionId | None = None
    created_at: datetime

    @model_validator(mode="after")
    def require_timezone(self) -> PuzzleIdentity:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone offset")
        return self


class Clue(MetadataModel):
    """Presentation text and provenance links for compiled constraints."""

    clue_id: ClueId
    text: str
    constraint_ids: tuple[ConstraintId, ...]
    locale: str
    template_id: str | None = None
    instructional_redundancy: bool = False


class DisplaySpec(MetadataModel):
    """Family-neutral presentation semantics, separate from solver authority."""

    locale: str = "en"
    accessibility_labels: tuple[tuple[str, str], ...] = ()


class GenerationLineage(MetadataModel):
    """Minimal lineage link retained when a complete generated spec is stored."""

    generation_id: GenerationId
    parent_revision_ids: tuple[PuzzleRevisionId, ...] = ()
    seed: int | None = None


class ProvenanceReference(MetadataModel):
    """A source entity or producing activity supporting the specification."""

    provenance_id: ProvenanceId
    kind: Literal["entity", "activity", "agent"]
    label: str


class ProvenanceBundle(MetadataModel):
    """Immutable provenance references attached to a puzzle revision."""

    references: tuple[ProvenanceReference, ...] = ()


class PuzzleSpec(MetadataModel):
    """Validated family-neutral contract for one complete puzzle revision."""

    identity: PuzzleIdentity
    domains: tuple[Domain, ...]
    variables: tuple[Variable, ...]
    constraints: tuple[Constraint, ...]
    clues: tuple[Clue, ...]
    givens: tuple[Atom, ...]
    display_spec: DisplaySpec
    generation_lineage: GenerationLineage | None = None
    provenance: ProvenanceBundle

    @model_validator(mode="after")
    def validate_references(self) -> PuzzleSpec:
        domain_ids = tuple(domain.domain_id for domain in self.domains)
        variable_ids = tuple(variable.variable_id for variable in self.variables)
        constraint_ids = tuple(constraint.constraint_id for constraint in self.constraints)
        clue_ids = tuple(clue.clue_id for clue in self.clues)

        self._require_unique("domain", domain_ids)
        self._require_unique("variable", variable_ids)
        self._require_unique("constraint", constraint_ids)
        self._require_unique("clue", clue_ids)

        domain_id_set = set(domain_ids)
        variable_id_set = set(variable_ids)
        constraint_id_set = set(constraint_ids)

        missing_domains = {
            variable.domain_id
            for variable in self.variables
            if variable.domain_id not in domain_id_set
        }
        if missing_domains:
            raise ValueError(f"variables reference unknown domains: {sorted(missing_domains)}")

        missing_clue_constraints = {
            constraint_id
            for clue in self.clues
            for constraint_id in clue.constraint_ids
            if constraint_id not in constraint_id_set
        }
        if missing_clue_constraints:
            raise ValueError(
                f"clues reference unknown constraints: {sorted(missing_clue_constraints)}"
            )

        for constraint in self.constraints:
            if isinstance(constraint, CompositeConstraint):
                missing = set(constraint.constraint_ids) - constraint_id_set
                if missing:
                    raise ValueError(
                        f"composite constraint references unknown constraints: {sorted(missing)}"
                    )

        missing_given_variables = {
            atom.variable_id
            for atom in self.givens
            if isinstance(atom, (AssignmentAtom, ExclusionAtom))
            and atom.variable_id not in variable_id_set
        }
        if missing_given_variables:
            raise ValueError(
                f"givens reference unknown variables: {sorted(missing_given_variables)}"
            )
        return self

    @staticmethod
    def _require_unique(kind: str, identifiers: tuple[str, ...]) -> None:
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"{kind} identifiers must be unique")
