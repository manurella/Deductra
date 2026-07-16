"""SQLite integration tests for the CR-002 append-only event store."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from deductra.domain.serialization import canonical_json
from deductra.memory.event_store import (
    DuplicateEventError,
    EventStore,
    StreamConflictError,
    StreamIntegrityError,
)
from deductra.memory.sqlite_store import SQLiteEventStore
from deductra.reasoning.events import EventEnvelope, ProducerRef, TraceCompleted, TraceStarted
from deductra.reasoning.integrity import GENESIS_EVENT_HASH, seal_event

NOW = datetime(2026, 7, 16, 9, 0, tzinfo=UTC)
TRACE_ID = "deductra:trace:sqlite-test"
PRODUCER = ProducerRef(
    producer_id="deductra:producer:test",
    kind="system",
    version="1.0.0",
)


def sealed_event(
    sequence_no: int,
    previous_hash: str,
    *,
    event_id: str | None = None,
) -> EventEnvelope:
    payload = (
        TraceStarted(puzzle_spec_hash="a" * 64)
        if sequence_no == 0
        else TraceCompleted(final_state_hash="b" * 64)
    )
    return seal_event(
        event_id=event_id or f"deductra:event:sqlite:{sequence_no}",
        trace_id=TRACE_ID,
        puzzle_revision_id="deductra:revision:sqlite:1",
        branch_id="deductra:branch:root",
        sequence_no=sequence_no,
        schema_version="1.0.0",
        occurred_at=NOW,
        producer=PRODUCER,
        correlation_id="deductra:correlation:sqlite",
        previous_event_hash=previous_hash,
        payload=payload,
    )


def test_sqlite_store_round_trip_and_ordered_replay(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    first = sealed_event(0, GENESIS_EVENT_HASH)
    second = sealed_event(1, first.event_hash)

    with SQLiteEventStore(database) as store:
        assert isinstance(store, EventStore)
        store.append(first)
        store.append(second)

        replayed = store.read_stream(TRACE_ID)
        assert replayed == (first, second)
        assert tuple(canonical_json(item) for item in replayed) == (
            canonical_json(first),
            canonical_json(second),
        )
        assert store.read_stream(TRACE_ID, after_sequence=0) == (second,)
        assert store.latest(TRACE_ID) == second
        assert store.verify_stream(TRACE_ID).valid


def test_store_rejects_duplicate_and_stale_head_appends(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    first = sealed_event(0, GENESIS_EVENT_HASH)
    next_event = sealed_event(1, first.event_hash)
    stale_event = sealed_event(1, first.event_hash, event_id="deductra:event:stale")

    with SQLiteEventStore(database) as store:
        store.append(first)
        with pytest.raises(DuplicateEventError):
            store.append(first)
        store.append(next_event)
        with pytest.raises(StreamConflictError):
            store.append(stale_event)


def test_store_rejects_invalid_genesis_without_leaving_partial_stream(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    invalid = sealed_event(1, GENESIS_EVENT_HASH)
    valid = sealed_event(0, GENESIS_EVENT_HASH)

    with SQLiteEventStore(database) as store:
        with pytest.raises(StreamConflictError):
            store.append(invalid)
        assert store.latest(TRACE_ID) is None
        store.append(valid)
        assert store.latest(TRACE_ID) == valid


def test_persistent_tampering_invalidates_changed_and_following_events(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    first = sealed_event(0, GENESIS_EVENT_HASH)
    second = sealed_event(1, first.event_hash)
    with SQLiteEventStore(database) as store:
        store.append(first)
        store.append(second)

    with closing(sqlite3.connect(database)) as connection:
        stored = connection.execute(
            "SELECT envelope_json FROM events WHERE sequence_no = 0"
        ).fetchone()
        assert stored is not None
        envelope = json.loads(stored[0])
        envelope["payload"]["puzzle_spec_hash"] = "c" * 64
        connection.execute(
            "UPDATE events SET envelope_json = ? WHERE sequence_no = 0",
            (json.dumps(envelope, separators=(",", ":"), sort_keys=True),),
        )
        connection.commit()

    with SQLiteEventStore(database) as store:
        verification = store.verify_stream(TRACE_ID)
        assert not verification.valid
        assert verification.first_invalid_sequence == 0
        assert verification.untrusted_sequences == (0, 1)
        with pytest.raises(StreamIntegrityError):
            store.read_stream(TRACE_ID, after_sequence=0)


def test_stream_head_tampering_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    first = sealed_event(0, GENESIS_EVENT_HASH)
    with SQLiteEventStore(database) as store:
        store.append(first)

    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE event_streams SET latest_event_hash = ? WHERE trace_id = ?",
            ("d" * 64, TRACE_ID),
        )
        connection.commit()

    with SQLiteEventStore(database) as store:
        verification = store.verify_stream(TRACE_ID)
        assert not verification.valid
        assert verification.reason == "stored_representation_invalid"
        assert verification.untrusted_sequences == (0,)
        with pytest.raises(StreamIntegrityError):
            store.read_stream(TRACE_ID)
