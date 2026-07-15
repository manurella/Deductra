"""Normalized facts used as givens and later reasoning conclusions."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from deductra.domain.base import DomainModel
from deductra.domain.ids import ValueId, VariableId


class AssignmentAtom(DomainModel):
    kind: Literal["assignment"] = "assignment"
    variable_id: VariableId
    value_id: ValueId


class ExclusionAtom(DomainModel):
    kind: Literal["exclusion"] = "exclusion"
    variable_id: VariableId
    value_id: ValueId


class RelationAtom(DomainModel):
    kind: Literal["relation"] = "relation"
    relation: str
    arguments: tuple[str, ...]


class AggregateAtom(DomainModel):
    kind: Literal["aggregate"] = "aggregate"
    operator: Literal["sum", "count", "min", "max", "parity"]
    members: tuple[str, ...]
    comparator: Literal["eq", "ne", "lt", "le", "gt", "ge"]
    target: int


class TruthAtom(DomainModel):
    kind: Literal["truth"] = "truth"
    proposition_id: str
    truth_value: bool


type Atom = Annotated[
    AssignmentAtom | ExclusionAtom | RelationAtom | AggregateAtom | TruthAtom,
    Field(discriminator="kind"),
]
