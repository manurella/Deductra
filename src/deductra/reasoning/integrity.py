"""Deterministic sealing and verification for reasoning-event hash chains."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from deductra.domain.ids import (
    AttemptId,
    BranchId,
    CausationId,
    CorrelationId,
    EventId,
    PuzzleRevisionId,
    TraceId,
)
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.events import EventEnvelope, ProducerRef, ReasoningEventPayload

GENESIS_EVENT_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class ChainVerification:
    """Immutable result describing trust in an ordered event sequence."""

    total_count: int
    first_invalid_sequence: int | None = None
    reason: str | None = None
    untrusted_sequences: tuple[int, ...] = ()

    @property
    def valid(self) -> bool:
        """Return whether every event is ordered and cryptographically intact."""
        return self.first_invalid_sequence is None


def compute_event_hash(event: EventEnvelope) -> str:
    """Hash every canonical envelope field except the digest being computed."""
    return canonical_sha256(event.model_dump(mode="json", exclude={"event_hash"}))


def seal_event(
    *,
    event_id: EventId,
    trace_id: TraceId,
    puzzle_revision_id: PuzzleRevisionId,
    branch_id: BranchId,
    sequence_no: int,
    schema_version: str,
    occurred_at: datetime,
    producer: ProducerRef,
    correlation_id: CorrelationId,
    previous_event_hash: str,
    payload: ReasoningEventPayload,
    attempt_id: AttemptId | None = None,
    causation_id: CausationId | None = None,
) -> EventEnvelope:
    """Create an event whose digest covers its complete canonical contents."""
    unsigned = EventEnvelope(
        event_id=event_id,
        trace_id=trace_id,
        attempt_id=attempt_id,
        puzzle_revision_id=puzzle_revision_id,
        branch_id=branch_id,
        sequence_no=sequence_no,
        event_type=payload.kind,
        schema_version=schema_version,
        occurred_at=occurred_at,
        producer=producer,
        causation_id=causation_id,
        correlation_id=correlation_id,
        previous_event_hash=previous_event_hash,
        event_hash=GENESIS_EVENT_HASH,
        payload=payload,
    )
    return unsigned.model_copy(update={"event_hash": compute_event_hash(unsigned)})


def verify_event(event: EventEnvelope) -> bool:
    """Return whether an event's stored digest matches its canonical contents."""
    return event.event_hash == compute_event_hash(event)


def verify_chain(events: Iterable[EventEnvelope]) -> ChainVerification:
    """Verify ordering, linkage, and hashes; distrust every event after first failure."""
    ordered = tuple(events)
    expected_previous = GENESIS_EVENT_HASH
    trace_id: TraceId | None = None
    puzzle_revision_id: PuzzleRevisionId | None = None

    for index, event in enumerate(ordered):
        reason: str | None = None
        if event.sequence_no != index:
            reason = "non_contiguous_sequence"
        elif event.previous_event_hash != expected_previous:
            reason = "previous_hash_mismatch"
        elif not verify_event(event):
            reason = "event_hash_mismatch"
        elif trace_id is not None and event.trace_id != trace_id:
            reason = "trace_id_mismatch"
        elif puzzle_revision_id is not None and event.puzzle_revision_id != puzzle_revision_id:
            reason = "puzzle_revision_mismatch"

        if reason is not None:
            return ChainVerification(
                total_count=len(ordered),
                first_invalid_sequence=event.sequence_no,
                reason=reason,
                untrusted_sequences=tuple(item.sequence_no for item in ordered[index:]),
            )

        trace_id = event.trace_id
        puzzle_revision_id = event.puzzle_revision_id
        expected_previous = event.event_hash

    return ChainVerification(total_count=len(ordered))
