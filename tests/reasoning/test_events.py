"""Contract tests for CR-002 event envelopes and integrity chains."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from deductra.reasoning.events import EventEnvelope, ProducerRef, TraceCompleted, TraceStarted
from deductra.reasoning.integrity import (
    GENESIS_EVENT_HASH,
    compute_event_hash,
    seal_event,
    verify_chain,
    verify_event,
)

NOW = datetime(2026, 7, 16, 8, 30, tzinfo=UTC)
PRODUCER = ProducerRef(
    producer_id="deductra:producer:test",
    kind="system",
    version="1.0.0",
)


def event(
    sequence_no: int,
    previous_event_hash: str,
    *,
    trace_id: str = "deductra:trace:test",
) -> EventEnvelope:
    """Build one sealed lifecycle event for integrity tests."""
    payload = (
        TraceStarted(puzzle_spec_hash="a" * 64)
        if sequence_no == 0
        else TraceCompleted(final_state_hash="b" * 64)
    )
    return seal_event(
        event_id=f"deductra:event:{sequence_no}",
        trace_id=trace_id,
        puzzle_revision_id="deductra:revision:test:1",
        branch_id="deductra:branch:root",
        sequence_no=sequence_no,
        schema_version="1.0.0",
        occurred_at=NOW,
        producer=PRODUCER,
        correlation_id="deductra:correlation:test",
        previous_event_hash=previous_event_hash,
        payload=payload,
    )


def test_event_round_trip_preserves_canonical_hash() -> None:
    sealed = event(0, GENESIS_EVENT_HASH)
    restored = EventEnvelope.model_validate_json(sealed.model_dump_json())
    assert restored == sealed
    assert verify_event(restored)
    assert compute_event_hash(restored) == restored.event_hash


def test_envelope_rejects_event_type_payload_disagreement() -> None:
    sealed = event(0, GENESIS_EVENT_HASH)
    payload = sealed.model_dump(mode="python")
    payload["event_type"] = "trace_completed"
    with pytest.raises(ValidationError, match=r"event_type must match payload\.kind"):
        EventEnvelope.model_validate(payload)


def test_hash_chain_marks_tampered_event_and_all_following_events_untrusted() -> None:
    first = event(0, GENESIS_EVENT_HASH)
    second = event(1, first.event_hash)
    third = event(2, second.event_hash)
    tampered = second.model_copy(update={"payload": TraceCompleted(final_state_hash="c" * 64)})

    verification = verify_chain((first, tampered, third))

    assert not verification.valid
    assert verification.first_invalid_sequence == 1
    assert verification.reason == "event_hash_mismatch"
    assert verification.untrusted_sequences == (1, 2)


def test_chain_rejects_non_contiguous_ordering() -> None:
    first = event(0, GENESIS_EVENT_HASH)
    skipped = event(2, first.event_hash)
    verification = verify_chain((first, skipped))
    assert verification.reason == "non_contiguous_sequence"
    assert verification.untrusted_sequences == (2,)
