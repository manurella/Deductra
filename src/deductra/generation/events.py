"""Tamper-evident lifecycle events for generated candidates."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, cast

from pydantic import Field, JsonValue, field_serializer, field_validator, model_validator

from deductra.domain.base import DomainModel, freeze_json, thaw_json
from deductra.domain.ids import CandidateId, GenerationEventId, GenerationId, GenerationRequestId
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.events import EventSchemaVersion, Sha256Digest

GENESIS_EVENT_HASH = "0" * 64


class GenerationEventType(StrEnum):
    """Complete CR-007 generation-lineage event vocabulary."""

    GENERATION_REQUESTED = "generation_requested"
    RECIPE_SELECTED = "recipe_selected"
    SEED_INITIALIZED = "seed_initialized"
    SOLUTION_CONSTRUCTED = "solution_constructed"
    STRUCTURE_CONSTRUCTED = "structure_constructed"
    CONSTRAINT_POOL_CONSTRUCTED = "constraint_pool_constructed"
    CANDIDATE_ASSEMBLED = "candidate_assembled"
    CONSTRAINT_ADDED = "constraint_added"
    CONSTRAINT_REMOVED = "constraint_removed"
    CANDIDATE_REPAIRED = "candidate_repaired"
    UNIQUENESS_VERIFICATION_REQUESTED = "uniqueness_verification_requested"
    UNIQUENESS_VERIFICATION_COMPLETED = "uniqueness_verification_completed"
    HUMAN_SOLVE_REQUESTED = "human_solve_requested"
    HUMAN_SOLVE_COMPLETED = "human_solve_completed"
    DIFFICULTY_EVALUATED = "difficulty_evaluated"
    CANONICALIZATION_COMPLETED = "canonicalization_completed"
    NOVELTY_EVALUATED = "novelty_evaluated"
    PRESENTATION_VALIDATED = "presentation_validated"
    CANDIDATE_ACCEPTED = "candidate_accepted"
    CANDIDATE_REJECTED = "candidate_rejected"
    CANDIDATE_QUARANTINED = "candidate_quarantined"


class GenerationLineageEvent(DomainModel):
    """One ordered, immutable event in a generation attempt."""

    event_id: GenerationEventId
    generation_id: GenerationId
    request_id: GenerationRequestId
    sequence_no: Annotated[int, Field(ge=0)]
    event_type: GenerationEventType
    schema_version: EventSchemaVersion
    occurred_at: datetime
    candidate_id: CandidateId | None = None
    parent_candidate_id: CandidateId | None = None
    previous_event_hash: Sha256Digest
    event_hash: Sha256Digest
    details: Mapping[str, JsonValue] = Field(default_factory=dict)

    @field_validator("details", mode="after")
    @classmethod
    def freeze_details(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        frozen = freeze_json(value)
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by field type
            raise TypeError("details must be a mapping")
        return cast(Mapping[str, JsonValue], frozen)

    @field_serializer("details")
    def serialize_details(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        thawed = thaw_json(value)
        if not isinstance(thawed, dict):  # pragma: no cover - guaranteed by field type
            raise TypeError("details must serialize as an object")
        return cast(dict[str, Any], thawed)

    @model_validator(mode="after")
    def validate_event(self) -> GenerationLineageEvent:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        if (
            self.sequence_no == 0
            and self.event_type is not GenerationEventType.GENERATION_REQUESTED
        ):
            raise ValueError("the first generation event must be generation_requested")
        if self.event_type is GenerationEventType.GENERATION_REQUESTED and self.candidate_id:
            raise ValueError("generation_requested cannot identify a candidate")
        if self.parent_candidate_id and not self.candidate_id:
            raise ValueError("parent_candidate_id requires candidate_id")
        return self


def compute_generation_event_hash(event: GenerationLineageEvent) -> str:
    """Hash an event without its self-referential digest field."""
    return canonical_sha256(event.model_dump(mode="json", exclude={"event_hash"}))


def seal_generation_event(
    *,
    event_id: GenerationEventId,
    generation_id: GenerationId,
    request_id: GenerationRequestId,
    sequence_no: int,
    event_type: GenerationEventType,
    schema_version: EventSchemaVersion,
    occurred_at: datetime,
    previous_event_hash: Sha256Digest,
    candidate_id: CandidateId | None = None,
    parent_candidate_id: CandidateId | None = None,
    details: Mapping[str, JsonValue] | None = None,
) -> GenerationLineageEvent:
    """Create an event with its canonical integrity digest."""
    unsigned = GenerationLineageEvent(
        event_id=event_id,
        generation_id=generation_id,
        request_id=request_id,
        sequence_no=sequence_no,
        event_type=event_type,
        schema_version=schema_version,
        occurred_at=occurred_at,
        candidate_id=candidate_id,
        parent_candidate_id=parent_candidate_id,
        previous_event_hash=previous_event_hash,
        event_hash=GENESIS_EVENT_HASH,
        details=details or {},
    )
    return unsigned.model_copy(update={"event_hash": compute_generation_event_hash(unsigned)})


def generation_event_chain_failures(
    events: tuple[GenerationLineageEvent, ...],
) -> tuple[str, ...]:
    """Return stable diagnostics for ordering, linkage, and integrity failures."""
    failures: list[str] = []
    previous_hash = GENESIS_EVENT_HASH
    generation_id = events[0].generation_id if events else None
    request_id = events[0].request_id if events else None
    for expected_sequence, event in enumerate(events):
        if event.sequence_no != expected_sequence:
            failures.append(f"{event.event_id}:sequence")
        if event.generation_id != generation_id or event.request_id != request_id:
            failures.append(f"{event.event_id}:stream")
        if event.previous_event_hash != previous_hash:
            failures.append(f"{event.event_id}:previous_hash")
        if event.event_hash != compute_generation_event_hash(event):
            failures.append(f"{event.event_id}:event_hash")
        previous_hash = event.event_hash
    return tuple(failures)
