"""Versioned, immutable envelopes for canonical reasoning events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from deductra.domain.atoms import Atom
from deductra.domain.base import DomainModel, MetadataModel
from deductra.domain.ids import (
    AttemptId,
    BranchId,
    CausationId,
    ContradictionId,
    CorrelationId,
    EventId,
    ProducerId,
    PuzzleRevisionId,
    StateId,
    TraceId,
    ValueId,
    VariableId,
)

type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type EventSchemaVersion = Annotated[str, Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")]
type ReasoningOrigin = Literal["given", "human_rule", "assumption", "search", "system"]


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


class CandidatesEliminated(MetadataModel):
    """Remove verified candidates from one variable's current domain."""

    kind: Literal["candidates_eliminated"] = "candidates_eliminated"
    variable_id: VariableId
    value_ids: tuple[ValueId, ...]
    source_state_hash: Sha256Digest
    result_state_id: StateId
    origin: ReasoningOrigin

    @model_validator(mode="after")
    def validate_candidates(self) -> CandidatesEliminated:
        if not self.value_ids:
            raise ValueError("candidate elimination must contain at least one value")
        if len(self.value_ids) != len(set(self.value_ids)):
            raise ValueError("candidate elimination values must be unique")
        return self


class ValueAssigned(MetadataModel):
    """Project one verified assignment into the immutable puzzle state."""

    kind: Literal["value_assigned"] = "value_assigned"
    variable_id: VariableId
    value_id: ValueId
    source_state_hash: Sha256Digest
    result_state_id: StateId
    origin: ReasoningOrigin


class BranchOpened(MetadataModel):
    """Open an explicit assumption or search branch from a retained parent state."""

    kind: Literal["branch_opened"] = "branch_opened"
    parent_branch_id: BranchId
    opened_from_state_hash: Sha256Digest
    assumption: Atom
    method: Literal["assumption", "search", "demonstration"]
    result_state_id: StateId


class ContradictionDetected(MetadataModel):
    """Mark the current branch contradictory without deleting its projection."""

    kind: Literal["contradiction_detected"] = "contradiction_detected"
    contradiction_id: ContradictionId
    source_state_hash: Sha256Digest
    result_state_id: StateId
    category: str


class BranchClosed(MetadataModel):
    """Close a retained non-root branch and return projection focus to its parent."""

    kind: Literal["branch_closed"] = "branch_closed"
    source_state_hash: Sha256Digest
    status: Literal["contradicted", "solved", "abandoned"]


type ReasoningEventPayload = Annotated[
    TraceStarted
    | PuzzleValidated
    | InitialStateCreated
    | TraceCompleted
    | TraceFailed
    | CandidatesEliminated
    | ValueAssigned
    | BranchOpened
    | ContradictionDetected
    | BranchClosed,
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
