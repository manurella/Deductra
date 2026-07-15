"""Discriminated common constraint catalogue."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from deductra.domain.base import MetadataModel
from deductra.domain.expressions import BooleanExpression
from deductra.domain.ids import ConstraintId, ValueId, VariableId


class ConstraintBase(MetadataModel):
    constraint_id: ConstraintId
    label: str
    source_clue_id: str | None = None
    severity: Literal["hard", "instructional"] = "hard"


class DomainConstraint(ConstraintBase):
    kind: Literal["domain"] = "domain"
    variable_id: VariableId
    allowed_value_ids: tuple[ValueId, ...]


class AllDifferentConstraint(ConstraintBase):
    kind: Literal["all_different"] = "all_different"
    variable_ids: tuple[VariableId, ...]


class ArithmeticConstraint(ConstraintBase):
    kind: Literal["arithmetic"] = "arithmetic"
    expression: BooleanExpression


class CardinalityConstraint(ConstraintBase):
    kind: Literal["cardinality"] = "cardinality"
    variable_ids: tuple[VariableId, ...]
    value_id: ValueId | None = None
    minimum: int
    maximum: int


class AssociationConstraint(ConstraintBase):
    kind: Literal["association"] = "association"
    left_variable_id: VariableId
    right_variable_id: VariableId


class OrderConstraint(ConstraintBase):
    kind: Literal["order"] = "order"
    before_variable_id: VariableId
    after_variable_id: VariableId
    strict: bool = True


class AdjacencyConstraint(ConstraintBase):
    kind: Literal["adjacency"] = "adjacency"
    left_variable_id: VariableId
    right_variable_id: VariableId


class DistanceConstraint(ConstraintBase):
    kind: Literal["distance"] = "distance"
    left_variable_id: VariableId
    right_variable_id: VariableId
    distance: int


class RegionConstraint(ConstraintBase):
    kind: Literal["region"] = "region"
    variable_ids: tuple[VariableId, ...]


class CageConstraint(ConstraintBase):
    kind: Literal["cage"] = "cage"
    variable_ids: tuple[VariableId, ...]
    operator: Literal["sum", "product", "difference", "quotient"]
    target: int


class SelectionConstraint(ConstraintBase):
    kind: Literal["selection"] = "selection"
    variable_ids: tuple[VariableId, ...]
    minimum: int
    maximum: int


class CapacityConstraint(ConstraintBase):
    kind: Literal["capacity"] = "capacity"
    variable_ids: tuple[VariableId, ...]
    capacity: int


class ImplicationConstraint(ConstraintBase):
    kind: Literal["implication"] = "implication"
    premise: BooleanExpression
    conclusion: BooleanExpression


class EquivalenceConstraint(ConstraintBase):
    kind: Literal["equivalence"] = "equivalence"
    left: BooleanExpression
    right: BooleanExpression


class PropositionConstraint(ConstraintBase):
    kind: Literal["proposition"] = "proposition"
    expression: BooleanExpression


class CompositeConstraint(ConstraintBase):
    kind: Literal["composite"] = "composite"
    operator: Literal["and", "or"]
    constraint_ids: tuple[ConstraintId, ...]

    @model_validator(mode="after")
    def reject_self_reference(self) -> CompositeConstraint:
        if self.constraint_id in self.constraint_ids:
            raise ValueError("a composite constraint cannot reference itself")
        return self


type Constraint = Annotated[
    DomainConstraint
    | AllDifferentConstraint
    | ArithmeticConstraint
    | CardinalityConstraint
    | AssociationConstraint
    | OrderConstraint
    | AdjacencyConstraint
    | DistanceConstraint
    | RegionConstraint
    | CageConstraint
    | SelectionConstraint
    | CapacityConstraint
    | ImplicationConstraint
    | EquivalenceConstraint
    | PropositionConstraint
    | CompositeConstraint,
    Field(discriminator="kind"),
]
