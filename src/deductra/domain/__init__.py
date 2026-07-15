"""Typed, family-neutral domain contracts for Deductra puzzles."""

from deductra.domain.atoms import (
    AggregateAtom,
    AssignmentAtom,
    Atom,
    ExclusionAtom,
    RelationAtom,
    TruthAtom,
)
from deductra.domain.constraints import Constraint
from deductra.domain.puzzle import PuzzleIdentity, PuzzleSpec
from deductra.domain.schema import puzzle_spec_json_schema, rendered_puzzle_spec_json_schema
from deductra.domain.serialization import canonical_json, canonical_json_bytes, canonical_sha256
from deductra.domain.values import Domain, DomainValue, Variable

__all__ = [
    "AggregateAtom",
    "AssignmentAtom",
    "Atom",
    "Constraint",
    "Domain",
    "DomainValue",
    "ExclusionAtom",
    "PuzzleIdentity",
    "PuzzleSpec",
    "RelationAtom",
    "TruthAtom",
    "Variable",
    "canonical_json",
    "canonical_json_bytes",
    "canonical_sha256",
    "puzzle_spec_json_schema",
    "rendered_puzzle_spec_json_schema",
]
