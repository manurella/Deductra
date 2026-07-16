"""Versioned, immutable envelopes for canonical reasoning events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from deductra.domain.base import DomainModel, MetadataModel
from deductra.domain.ids import (
    AttemptId,
    BranchId,
    CausationId,
    CorrelationId,
    EventId,
    ProducerId,
    PuzzleRevisionId,
    TraceId,
)

type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type EventSchemaVersion = Annotated[str, Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")]


class ProducerRef(MetadataModel):
    """Identity of the deterministic component that emitted an event."""

    producer_id: ProducerId
    kind: Literal["system", "human", "rule_engine", "solver", "tool", "agent"]
    version: str


class TraceStarted(MetadataModel):
    """Begin a canonical reasoning trace for one immutable puzzle revision."""

    kind: Literal["trace_started"] = "trace_started"
    puzzle_spec_hash: Sha256Digest


class PuzzleValidated(MetadataModel):
    """Record successful structural validation of the puzzle specification."""

    kind: Literal["puzzle_validated"] = "puzzle_validated"
    puzzle_spec_hash: Sha256Digest


class InitialStateCreated(MetadataModel):
    """Identify the immutable genesis state prepared for later reduction."""

    kind: Literal["initial_state_created"] = "initial_state_created"
    state_hash: Sha256Digest


class TraceCompleted(MetadataModel):
    """Close a trace after its final state has been persisted."""

    kind: Literal["trace_completed"] = "trace_completed"
    final_state_hash: Sha256Digest


class TraceFailed(MetadataModel):
    """Close a trace with a stable machine-readable failure classification."""

    kind: Literal["trace_failed"] = "trace_failed"
    error_code: str
    message: str


type ReasoningEventPayload = Annotated[
    TraceStarted | PuzzleValidated | InitialStateCreated | TraceCompleted | TraceFailed,
    Field(discriminator="kind"),
]


class EventEnvelope(DomainModel):
    """Canonical event plus ordering, causality, provenance, and integrity fields."""

    event_id: EventId
    trace_id: TraceId
    attempt_id: AttemptId | None = None
    puzzle_revision_id: PuzzleRevisionId
    branch_id: BranchId
    sequence_no: Annotated[int, Field(ge=0)]
    event_type: str
    schema_version: EventSchemaVersion
    occurred_at: datetime
    producer: ProducerRef
    causation_id: CausationId | None = None
    correlation_id: CorrelationId
    previous_event_hash: Sha256Digest
    event_hash: Sha256Digest
    payload: ReasoningEventPayload

    @model_validator(mode="after")
    def validate_envelope_contract(self) -> EventEnvelope:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        if self.event_type != self.payload.kind:
            raise ValueError("event_type must match payload.kind")
        return self
