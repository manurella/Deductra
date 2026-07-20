"""Local Logic Grid attempt evidence and persistence contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Protocol, cast, runtime_checkable

from pydantic import StringConstraints, model_validator

from deductra.domain.base import DomainModel
from deductra.domain.ids import AttemptId, EventId, UserId
from deductra.domain.serialization import canonical_sha256
from deductra.families.logic_grid.play import (
    PLAY_GENESIS_HASH,
    CheckCompletion,
    LogicGridPlaySession,
    PlayEvent,
    PlaySessionStatus,
)
from deductra.families.logic_grid.specification import LogicGridSpec
from deductra.memory.projections.events import (
    PROJECTION_GENESIS_HASH,
    AttemptCompleted,
    AttemptStarted,
    ProjectionEvent,
    ProjectionStreamKind,
    seal_projection_event,
)
from deductra.memory.projections.model import AttemptProjection
from deductra.memory.projections.rebuild import rebuild_attempt_projection

ATTEMPT_RECORD_SCHEMA_VERSION = "1.0.0"
type Sha256Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type PlayActionKind = Literal[
    "assign_cell",
    "exclude_cell",
    "clear_cell",
    "undo_move",
    "redo_move",
    "check_completion",
    "validate_progress",
    "pause_session",
    "resume_session",
    "create_checkpoint",
    "restore_checkpoint",
]


class AttemptStoreError(RuntimeError):
    """Base error for durable Logic Grid attempt operations."""


class AttemptAlreadyExistsError(AttemptStoreError):
    """Raised when an attempt identity already belongs to a stored stream."""


class AttemptConflictError(AttemptStoreError):
    """Raised when an append does not continue the durable stream head."""


class AttemptIntegrityError(AttemptStoreError):
    """Raised when persisted attempt evidence cannot be trusted."""


class ObservedPlayEvent(DomainModel):
    """One play event paired with its local observation time."""

    event: PlayEvent
    occurred_at: datetime
    observation_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_observation(self) -> ObservedPlayEvent:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        if self.observation_hash != compute_observation_hash(self):
            raise ValueError("observation_hash does not match the observed play event")
        return self


class PlayActionEvidence(DomainModel):
    """Descriptive action counts without correctness or mastery meaning."""

    kind: PlayActionKind
    accepted_actions: int
    rejected_actions: int
    source_event_ids: tuple[EventId, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> PlayActionEvidence:
        if self.accepted_actions < 0 or self.rejected_actions < 0:
            raise ValueError("action counts cannot be negative")
        if self.accepted_actions + self.rejected_actions != len(self.source_event_ids):
            raise ValueError("action counts must equal the referenced source events")
        if len(self.source_event_ids) != len(set(self.source_event_ids)):
            raise ValueError("action evidence event identifiers must be unique")
        return self


class LogicGridAttemptEvidence(DomainModel):
    """Disposable descriptive view rebuilt exactly from one play session."""

    attempt_id: AttemptId
    user_id: UserId
    puzzle_revision_id: str
    status: PlaySessionStatus
    total_actions: int
    accepted_actions: int
    rejected_actions: int
    action_evidence: tuple[PlayActionEvidence, ...]
    source_event_ids: tuple[EventId, ...]
    source_head_hash: Sha256Digest
    source_session_hash: Sha256Digest
    projection_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_projection(self) -> LogicGridAttemptEvidence:
        if min(self.total_actions, self.accepted_actions, self.rejected_actions) < 0:
            raise ValueError("attempt action counts cannot be negative")
        if self.total_actions != self.accepted_actions + self.rejected_actions:
            raise ValueError("attempt action totals are inconsistent")
        if self.total_actions != len(self.source_event_ids):
            raise ValueError("attempt total must equal its source event count")
        if tuple(item.kind for item in self.action_evidence) != tuple(
            sorted(item.kind for item in self.action_evidence)
        ):
            raise ValueError("action evidence must use canonical kind order")
        grouped_ids = tuple(
            event_id for item in self.action_evidence for event_id in item.source_event_ids
        )
        if set(grouped_ids) != set(self.source_event_ids) or len(grouped_ids) != len(
            self.source_event_ids
        ):
            raise ValueError("action evidence must partition every source event exactly once")
        if self.projection_hash != compute_attempt_evidence_hash(self):
            raise ValueError("projection_hash does not match the attempt evidence")
        return self


class PersistedLogicGridAttempt(DomainModel):
    """Validated durable view of one local attempt and its derived evidence."""

    schema_version: Literal["1.0.0"] = ATTEMPT_RECORD_SCHEMA_VERSION
    user_id: UserId
    started_at: datetime
    updated_at: datetime
    observations: tuple[ObservedPlayEvent, ...]
    session: LogicGridPlaySession
    evidence: LogicGridAttemptEvidence
    projection_events: tuple[ProjectionEvent, ...]
    attempt_projection: AttemptProjection
    record_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_record(self) -> PersistedLogicGridAttempt:
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("started_at must include a timezone offset")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("updated_at must include a timezone offset")
        if self.updated_at < self.started_at:
            raise ValueError("updated_at cannot precede started_at")
        if tuple(item.event for item in self.observations) != self.session.events:
            raise ValueError("observations must correspond exactly to the play event stream")
        observation_times = tuple(item.occurred_at for item in self.observations)
        if observation_times != tuple(sorted(observation_times)):
            raise ValueError("play observations must use chronological order")
        expected_updated = observation_times[-1] if observation_times else self.started_at
        if self.updated_at != expected_updated:
            raise ValueError("updated_at must equal the latest durable observation time")
        expected_evidence = build_logic_grid_attempt_evidence(
            self.session,
            user_id=self.user_id,
        )
        if self.evidence != expected_evidence:
            raise ValueError("attempt evidence does not equal a clean play replay projection")
        expected_events = build_attempt_projection_events(
            self.session,
            user_id=self.user_id,
            started_at=self.started_at,
            observations=self.observations,
        )
        if self.projection_events != expected_events:
            raise ValueError("memory events do not equal normalized play lifecycle evidence")
        if rebuild_attempt_projection(self.projection_events) != self.attempt_projection:
            raise ValueError("attempt projection does not equal its normalized event replay")
        if self.record_hash != compute_attempt_record_hash(self):
            raise ValueError("record_hash does not match the persisted attempt")
        return self


@runtime_checkable
class LogicGridAttemptStore(Protocol):
    """Persistence port for exact local Logic Grid attempt replay."""

    def create(
        self,
        puzzle: LogicGridSpec,
        session: LogicGridPlaySession,
        *,
        user_id: UserId,
        occurred_at: datetime,
    ) -> PersistedLogicGridAttempt:
        """Create one empty durable attempt stream."""
        ...

    def append(
        self,
        puzzle: LogicGridSpec,
        session: LogicGridPlaySession,
        *,
        occurred_at: datetime,
    ) -> PersistedLogicGridAttempt:
        """Atomically append the one new event carried by ``session``."""
        ...

    def read(
        self,
        puzzle: LogicGridSpec,
        attempt_id: AttemptId,
    ) -> PersistedLogicGridAttempt | None:
        """Read and fully verify one stored attempt."""
        ...

    def close(self) -> None:
        """Release resources owned by the store."""
        ...


def compute_observation_hash(observation: ObservedPlayEvent) -> str:
    """Hash an event and local observation time without its digest field."""
    return canonical_sha256(observation.model_dump(mode="json", exclude={"observation_hash"}))


def observe_play_event(event: PlayEvent, *, occurred_at: datetime) -> ObservedPlayEvent:
    """Seal a timezone-aware local observation of one canonical play event."""
    unsigned = ObservedPlayEvent.model_construct(
        event=event,
        occurred_at=occurred_at,
        observation_hash=PLAY_GENESIS_HASH,
    )
    return ObservedPlayEvent(
        event=event,
        occurred_at=occurred_at,
        observation_hash=compute_observation_hash(unsigned),
    )


def compute_attempt_evidence_hash(evidence: LogicGridAttemptEvidence) -> str:
    return canonical_sha256(evidence.model_dump(mode="json", exclude={"projection_hash"}))


def build_logic_grid_attempt_evidence(
    session: LogicGridPlaySession,
    *,
    user_id: UserId,
) -> LogicGridAttemptEvidence:
    """Rebuild non-evaluative action evidence from canonical play history."""
    by_kind: dict[str, list[PlayEvent]] = {}
    for event in session.events:
        by_kind.setdefault(event.action.kind, []).append(event)
    action_evidence = tuple(
        PlayActionEvidence(
            kind=cast(PlayActionKind, kind),
            accepted_actions=sum(item.accepted for item in events),
            rejected_actions=sum(not item.accepted for item in events),
            source_event_ids=tuple(item.event_id for item in events),
        )
        for kind, events in sorted(by_kind.items())
    )
    source_head_hash = session.events[-1].event_hash if session.events else PLAY_GENESIS_HASH
    values = {
        "attempt_id": session.attempt_id,
        "user_id": user_id,
        "puzzle_revision_id": session.puzzle_revision_id,
        "status": session.status,
        "total_actions": len(session.events),
        "accepted_actions": sum(item.accepted for item in session.events),
        "rejected_actions": sum(not item.accepted for item in session.events),
        "action_evidence": action_evidence,
        "source_event_ids": tuple(item.event_id for item in session.events),
        "source_head_hash": source_head_hash,
        "source_session_hash": session.session_hash,
    }
    return LogicGridAttemptEvidence.model_validate(
        {**values, "projection_hash": canonical_sha256(values)}
    )


def _projection_stream_id(attempt_id: AttemptId) -> str:
    return f"deductra:projection:attempt:{canonical_sha256({'attempt_id': attempt_id})}"


def _projection_event_id(attempt_id: AttemptId, source: str) -> str:
    digest = canonical_sha256({"attempt_id": attempt_id, "source": source})
    return f"deductra:projection:event:{digest}"


def build_attempt_projection_events(
    session: LogicGridPlaySession,
    *,
    user_id: UserId,
    started_at: datetime,
    observations: tuple[ObservedPlayEvent, ...],
) -> tuple[ProjectionEvent, ...]:
    """Normalize only authoritative attempt lifecycle facts for common memory."""
    stream_id = _projection_stream_id(session.attempt_id)
    started = seal_projection_event(
        event_id=_projection_event_id(session.attempt_id, "started"),
        stream_id=stream_id,
        stream_kind=ProjectionStreamKind.ATTEMPT,
        sequence_no=0,
        schema_version="1.0.0",
        occurred_at=started_at,
        previous_event_hash=PROJECTION_GENESIS_HASH,
        payload=AttemptStarted(
            attempt_id=session.attempt_id,
            user_id=user_id,
            puzzle_revision_id=session.puzzle_revision_id,
        ),
    )
    events = [started]
    completion = next(
        (
            observation
            for observation in observations
            if observation.event.accepted
            and observation.event.code == "completed"
            and isinstance(observation.event.action, CheckCompletion)
        ),
        None,
    )
    if completion is not None:
        events.append(
            seal_projection_event(
                event_id=_projection_event_id(
                    session.attempt_id,
                    f"completed:{completion.event.event_hash}",
                ),
                stream_id=stream_id,
                stream_kind=ProjectionStreamKind.ATTEMPT,
                sequence_no=1,
                schema_version="1.0.0",
                occurred_at=completion.occurred_at,
                previous_event_hash=started.event_hash,
                payload=AttemptCompleted(attempt_id=session.attempt_id),
            )
        )
    return tuple(events)


def compute_attempt_record_hash(record: PersistedLogicGridAttempt) -> str:
    return canonical_sha256(record.model_dump(mode="json", exclude={"record_hash"}))


def build_persisted_logic_grid_attempt(
    session: LogicGridPlaySession,
    *,
    user_id: UserId,
    started_at: datetime,
    observations: tuple[ObservedPlayEvent, ...],
) -> PersistedLogicGridAttempt:
    """Build and seal the complete verified durable attempt view."""
    updated_at = observations[-1].occurred_at if observations else started_at
    evidence = build_logic_grid_attempt_evidence(session, user_id=user_id)
    projection_events = build_attempt_projection_events(
        session,
        user_id=user_id,
        started_at=started_at,
        observations=observations,
    )
    attempt_projection = rebuild_attempt_projection(projection_events)
    values = {
        "schema_version": ATTEMPT_RECORD_SCHEMA_VERSION,
        "user_id": user_id,
        "started_at": started_at,
        "updated_at": updated_at,
        "observations": observations,
        "session": session,
        "evidence": evidence,
        "projection_events": projection_events,
        "attempt_projection": attempt_projection,
    }
    unsigned = PersistedLogicGridAttempt.model_construct(
        schema_version=ATTEMPT_RECORD_SCHEMA_VERSION,
        user_id=user_id,
        started_at=started_at,
        updated_at=updated_at,
        observations=observations,
        session=session,
        evidence=evidence,
        projection_events=projection_events,
        attempt_projection=attempt_projection,
        record_hash=PLAY_GENESIS_HASH,
    )
    return PersistedLogicGridAttempt.model_validate(
        {**values, "record_hash": compute_attempt_record_hash(unsigned)}
    )
