"""Reproducible candidate lineage assembled from immutable generation events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from pydantic import Field, JsonValue, field_serializer, field_validator, model_validator

from deductra.domain.base import DomainModel, freeze_json, thaw_json
from deductra.domain.ids import (
    CandidateId,
    GenerationEventId,
    GenerationId,
    GenerationRequestId,
    RecipeId,
)
from deductra.generation.events import (
    GenerationEventType,
    GenerationLineageEvent,
    generation_event_chain_failures,
)


class CandidateLineage(DomainModel):
    """Identity and deterministic construction inputs for one candidate revision."""

    candidate_id: CandidateId
    parent_candidate_id: CandidateId | None
    recipe_id: RecipeId
    recipe_version: str
    seed: int
    mutation_operator: str | None = None
    operation_parameters: Mapping[str, JsonValue] = Field(default_factory=dict)
    created_event_id: GenerationEventId

    @field_validator("operation_parameters", mode="after")
    @classmethod
    def freeze_parameters(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        frozen = freeze_json(value)
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by field type
            raise TypeError("operation_parameters must be a mapping")
        return cast(Mapping[str, JsonValue], frozen)

    @field_serializer("operation_parameters")
    def serialize_parameters(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        thawed = thaw_json(value)
        if not isinstance(thawed, dict):  # pragma: no cover - guaranteed by field type
            raise TypeError("operation_parameters must serialize as an object")
        return cast(dict[str, Any], thawed)

    @model_validator(mode="after")
    def validate_parent(self) -> CandidateLineage:
        if self.parent_candidate_id == self.candidate_id:
            raise ValueError("a candidate cannot be its own parent")
        return self


class GenerationLineage(DomainModel):
    """Complete replay metadata and event history for one generation request."""

    generation_id: GenerationId
    request_id: GenerationRequestId
    generator_version: str
    rng_provider: str
    rng_version: str
    dependency_versions: tuple[tuple[str, str], ...] = ()
    candidates: tuple[CandidateLineage, ...]
    events: tuple[GenerationLineageEvent, ...]

    @model_validator(mode="after")
    def validate_lineage(self) -> GenerationLineage:
        if not self.events:
            raise ValueError("generation lineage requires at least one event")
        failures = generation_event_chain_failures(self.events)
        if failures:
            raise ValueError(f"generation event chain is invalid: {list(failures)}")
        if any(
            event.generation_id != self.generation_id or event.request_id != self.request_id
            for event in self.events
        ):
            raise ValueError("lineage event stream identity must match the lineage")

        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate identifiers must be unique")
        event_by_id = {event.event_id: event for event in self.events}
        candidate_id_set = set(candidate_ids)
        for candidate in self.candidates:
            created = event_by_id.get(candidate.created_event_id)
            if (
                created is None
                or created.event_type is not GenerationEventType.CANDIDATE_ASSEMBLED
                or created.candidate_id != candidate.candidate_id
            ):
                raise ValueError("candidate created_event_id must resolve to its assembly event")
            if (
                candidate.parent_candidate_id is not None
                and candidate.parent_candidate_id not in candidate_id_set
            ):
                raise ValueError("candidate parent must resolve within the lineage")
        return self
