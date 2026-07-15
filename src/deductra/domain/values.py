"""Family-neutral domains, values, and variables."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from pydantic import model_validator

from deductra.domain.base import MetadataModel
from deductra.domain.ids import DomainId, ValueId, VariableId


class DomainValue(MetadataModel):
    """A labelled member of a puzzle domain."""

    value_id: ValueId
    label: str
    ordinal: int | None = None
    numeric_value: int | Fraction | None = None
    symbol: str | None = None


class Domain(MetadataModel):
    """An immutable collection of values available to variables."""

    domain_id: DomainId
    values: tuple[DomainValue, ...]
    ordered: bool
    distinct_by_default: bool = False

    @model_validator(mode="after")
    def validate_unique_values(self) -> Domain:
        value_ids = tuple(value.value_id for value in self.values)
        if len(value_ids) != len(set(value_ids)):
            raise ValueError("domain value identifiers must be unique")
        if not value_ids:
            raise ValueError("a domain must contain at least one value")
        return self


class Variable(MetadataModel):
    """A named unknown whose candidates come from one domain."""

    variable_id: VariableId
    label: str
    domain_id: DomainId
    role: Literal["cell", "entity_assignment", "position", "selection", "answer", "arithmetic"]
    coordinates: tuple[int, ...] | None = None
