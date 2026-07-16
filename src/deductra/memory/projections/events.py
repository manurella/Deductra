"""Typed, tamper-evident source events for rebuildable memory projections."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from deductra.domain.base import DomainModel, MetadataModel
from deductra.domain.ids import (
    ArtifactId,
    AttemptId,
    CandidateId,
    EventId,
    ProjectionStreamId,
    PuzzleId,
    PuzzleRevisionId,
    RuleId,
    UserId,
)
from deductra.domain.serialization import canonical_sha256
from deductra.generation.contracts import PuzzleFingerprints
from deductra.reasoning.events import EventSchemaVersion, Sha256Digest

PROJECTION_GENESIS_HASH = "0" * 64


class ProjectionStreamKind(StrEnum):
    """Separate stream authorities whose events feed derived projections."""

    ATTEMPT = "attempt"
    NOVELTY = "novelty"
    ARTIFACT = "artifact"


class AttemptStarted(MetadataModel):
    kind: Literal["attempt_started"] = "attempt_started"
    attempt_id: AttemptId
    user_id: UserId
    puzzle_revision_id: PuzzleRevisionId


class MoveEvaluated(MetadataModel):
    kind: Literal["move_evaluated"] = "move_evaluated"
    attempt_id: AttemptId
    outcome: Literal["accepted", "rejected"]
    rule_id: RuleId | None = None
    duration_ms: Annotated[int, Field(ge=0)]


class HintRevealed(MetadataModel):
    kind: Literal["hint_revealed"] = "hint_revealed"
    attempt_id: AttemptId
    rule_id: RuleId | None = None


class StepExplained(MetadataModel):
    kind: Literal["step_explained"] = "step_explained"
    attempt_id: AttemptId
    rule_id: RuleId


class AttemptCompleted(MetadataModel):
    kind: Literal["attempt_completed"] = "attempt_completed"
    attempt_id: AttemptId


class AttemptAbandoned(MetadataModel):
    kind: Literal["attempt_abandoned"] = "attempt_abandoned"
    attempt_id: AttemptId


class SelfAssessmentRecorded(MetadataModel):
    kind: Literal["self_assessment_recorded"] = "self_assessment_recorded"
    attempt_id: AttemptId
    rating: Annotated[int, Field(ge=1, le=5)]


class ReplayViewed(MetadataModel):
    kind: Literal["replay_viewed"] = "replay_viewed"
    attempt_id: AttemptId


class NoveltyEntryRecorded(MetadataModel):
    kind: Literal["novelty_entry_recorded"] = "novelty_entry_recorded"
    puzzle_id: PuzzleId
    puzzle_revision_id: PuzzleRevisionId
    candidate_id: CandidateId
    fingerprints: PuzzleFingerprints
    evidence_ids: tuple[str, ...]


class NoveltyEntryRemoved(MetadataModel):
    kind: Literal["novelty_entry_removed"] = "novelty_entry_removed"
    puzzle_revision_id: PuzzleRevisionId
    reason: str


class ArtifactRecorded(MetadataModel):
    kind: Literal["artifact_recorded"] = "artifact_recorded"
    artifact_id: ArtifactId
    puzzle_revision_id: PuzzleRevisionId
    artifact_kind: Literal["report", "image", "export", "trace", "hypergraph", "other"]
    media_type: str
    content_hash: Sha256Digest
    evidence_ids: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()


class ArtifactSuperseded(MetadataModel):
    kind: Literal["artifact_superseded"] = "artifact_superseded"
    artifact_id: ArtifactId
    replacement_artifact_id: ArtifactId


class ArtifactRemoved(MetadataModel):
    kind: Literal["artifact_removed"] = "artifact_removed"
    artifact_id: ArtifactId
    reason: str


type ProjectionEventPayload = Annotated[
    AttemptStarted
    | MoveEvaluated
    | HintRevealed
    | StepExplained
    | AttemptCompleted
    | AttemptAbandoned
    | SelfAssessmentRecorded
    | ReplayViewed
    | NoveltyEntryRecorded
    | NoveltyEntryRemoved
    | ArtifactRecorded
    | ArtifactSuperseded
    | ArtifactRemoved,
    Field(discriminator="kind"),
]


class ProjectionEvent(DomainModel):
    """Canonical event envelope used solely to rebuild disposable indexes."""

    event_id: EventId
    stream_id: ProjectionStreamId
    stream_kind: ProjectionStreamKind
    sequence_no: Annotated[int, Field(ge=0)]
    schema_version: EventSchemaVersion
    occurred_at: datetime
    previous_event_hash: Sha256Digest
    event_hash: Sha256Digest
    payload: ProjectionEventPayload

    @model_validator(mode="after")
    def validate_envelope(self) -> ProjectionEvent:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        expected_stream = (
            ProjectionStreamKind.ATTEMPT
            if isinstance(
                self.payload,
                (
                    AttemptStarted,
                    MoveEvaluated,
                    HintRevealed,
                    StepExplained,
                    AttemptCompleted,
                    AttemptAbandoned,
                    SelfAssessmentRecorded,
                    ReplayViewed,
                ),
            )
            else (
                ProjectionStreamKind.NOVELTY
                if isinstance(self.payload, (NoveltyEntryRecorded, NoveltyEntryRemoved))
                else ProjectionStreamKind.ARTIFACT
            )
        )
        if self.stream_kind is not expected_stream:
            raise ValueError("payload type does not belong to the declared projection stream")
        if (
            self.sequence_no == 0
            and self.stream_kind is ProjectionStreamKind.ATTEMPT
            and not isinstance(self.payload, AttemptStarted)
        ):
            raise ValueError("attempt streams must begin with attempt_started")
        return self


def compute_projection_event_hash(event: ProjectionEvent) -> str:
    return canonical_sha256(event.model_dump(mode="json", exclude={"event_hash"}))


def seal_projection_event(
    *,
    event_id: EventId,
    stream_id: ProjectionStreamId,
    stream_kind: ProjectionStreamKind,
    sequence_no: int,
    schema_version: EventSchemaVersion,
    occurred_at: datetime,
    previous_event_hash: Sha256Digest,
    payload: ProjectionEventPayload,
) -> ProjectionEvent:
    unsigned = ProjectionEvent(
        event_id=event_id,
        stream_id=stream_id,
        stream_kind=stream_kind,
        sequence_no=sequence_no,
        schema_version=schema_version,
        occurred_at=occurred_at,
        previous_event_hash=previous_event_hash,
        event_hash=PROJECTION_GENESIS_HASH,
        payload=payload,
    )
    return unsigned.model_copy(update={"event_hash": compute_projection_event_hash(unsigned)})


def projection_event_chain_failures(events: tuple[ProjectionEvent, ...]) -> tuple[str, ...]:
    """Return deterministic stream integrity diagnostics."""
    failures: list[str] = []
    previous_hash = PROJECTION_GENESIS_HASH
    stream_id = events[0].stream_id if events else None
    stream_kind = events[0].stream_kind if events else None
    seen_event_ids: set[EventId] = set()
    for expected_sequence, event in enumerate(events):
        if event.event_id in seen_event_ids:
            failures.append(f"{event.event_id}:duplicate")
        seen_event_ids.add(event.event_id)
        if event.sequence_no != expected_sequence:
            failures.append(f"{event.event_id}:sequence")
        if event.stream_id != stream_id or event.stream_kind is not stream_kind:
            failures.append(f"{event.event_id}:stream")
        if event.previous_event_hash != previous_hash:
            failures.append(f"{event.event_id}:previous_hash")
        if event.event_hash != compute_projection_event_hash(event):
            failures.append(f"{event.event_id}:event_hash")
        previous_hash = event.event_hash
    return tuple(failures)
