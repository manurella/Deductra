"""Transactional SQLite adapter for the canonical event-store port."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from pydantic import ValidationError

from deductra.domain.ids import TraceId
from deductra.domain.serialization import canonical_json
from deductra.memory.event_store import (
    DuplicateEventError,
    StreamConflictError,
    StreamIntegrityError,
)
from deductra.reasoning.events import EventEnvelope
from deductra.reasoning.integrity import (
    GENESIS_EVENT_HASH,
    ChainVerification,
    verify_chain,
    verify_event,
)

SCHEMA_VERSION = 1
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS event_streams (
    trace_id TEXT PRIMARY KEY,
    puzzle_revision_id TEXT NOT NULL,
    latest_sequence INTEGER NOT NULL CHECK (latest_sequence >= 0),
    latest_event_hash TEXT NOT NULL CHECK (length(latest_event_hash) = 64),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL REFERENCES event_streams(trace_id),
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    previous_event_hash TEXT NOT NULL CHECK (length(previous_event_hash) = 64),
    event_hash TEXT NOT NULL UNIQUE CHECK (length(event_hash) = 64),
    envelope_json TEXT NOT NULL,
    UNIQUE (trace_id, sequence_no)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_events_trace_sequence
ON events(trace_id, sequence_no);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
) STRICT;
"""


class _StoredRepresentationError(StreamIntegrityError):
    """Internal error retaining the exact damaged persistent sequence."""

    def __init__(self, sequence_no: int, message: str) -> None:
        super().__init__(message)
        self.sequence_no = sequence_no


class SQLiteEventStore:
    """Single-connection SQLite event store with explicit atomic appends."""

    def __init__(self, database: str | Path) -> None:
        self._connection = sqlite3.connect(database, autocommit=True)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if str(database) != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        self._connection.executescript(SCHEMA_SQL)
        self._connection.execute(
            """
            INSERT OR IGNORE INTO schema_migrations(version, applied_at)
            VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (SCHEMA_VERSION,),
        )

    def append(self, event: EventEnvelope) -> None:
        """Atomically append one event after checking stream continuity and integrity."""
        if not verify_event(event):
            raise StreamIntegrityError("event_hash does not match the canonical envelope")

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            existing_events = self._load_stream(event.trace_id)
            verification = verify_chain(existing_events)
            if not verification.valid:
                raise StreamIntegrityError(
                    f"existing stream is invalid at sequence {verification.first_invalid_sequence}"
                )
            if any(existing.event_id == event.event_id for existing in existing_events):
                raise DuplicateEventError("event identifier already exists")

            stream = self._connection.execute(
                """
                SELECT puzzle_revision_id, latest_sequence, latest_event_hash
                FROM event_streams
                WHERE trace_id = ?
                """,
                (event.trace_id,),
            ).fetchone()

            if stream is None:
                self._validate_genesis(event)
                self._connection.execute(
                    """
                    INSERT INTO event_streams(
                        trace_id,
                        puzzle_revision_id,
                        latest_sequence,
                        latest_event_hash,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event.trace_id,
                        event.puzzle_revision_id,
                        event.sequence_no,
                        event.event_hash,
                        event.occurred_at.isoformat(),
                    ),
                )
            else:
                self._validate_continuation(event, cast(sqlite3.Row, stream))

            self._connection.execute(
                """
                INSERT INTO events(
                    event_id,
                    trace_id,
                    sequence_no,
                    event_type,
                    occurred_at,
                    previous_event_hash,
                    event_hash,
                    envelope_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.trace_id,
                    event.sequence_no,
                    event.event_type,
                    event.occurred_at.isoformat(),
                    event.previous_event_hash,
                    event.event_hash,
                    canonical_json(event),
                ),
            )
            self._connection.execute(
                """
                UPDATE event_streams
                SET latest_sequence = ?, latest_event_hash = ?
                WHERE trace_id = ?
                """,
                (event.sequence_no, event.event_hash, event.trace_id),
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise DuplicateEventError(
                "event identifier or stream sequence already exists"
            ) from error
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    @staticmethod
    def _validate_genesis(event: EventEnvelope) -> None:
        if event.sequence_no != 0 or event.previous_event_hash != GENESIS_EVENT_HASH:
            raise StreamConflictError("a new stream must begin at sequence 0 with the genesis hash")

    @staticmethod
    def _validate_continuation(event: EventEnvelope, stream: sqlite3.Row) -> None:
        latest_sequence = cast(int, stream["latest_sequence"])
        latest_hash = cast(str, stream["latest_event_hash"])
        puzzle_revision_id = cast(str, stream["puzzle_revision_id"])
        if event.puzzle_revision_id != puzzle_revision_id:
            raise StreamConflictError("puzzle revision cannot change within a trace")
        if event.sequence_no != latest_sequence + 1:
            raise StreamConflictError("event sequence does not continue the stream head")
        if event.previous_event_hash != latest_hash:
            raise StreamConflictError("previous_event_hash does not match the stream head")

    def _load_rows(self, trace_id: TraceId, *, after_sequence: int = -1) -> tuple[sqlite3.Row, ...]:
        cursor = self._connection.execute(
            """
            SELECT
                event_id,
                trace_id,
                sequence_no,
                previous_event_hash,
                event_hash,
                envelope_json
            FROM events
            WHERE trace_id = ? AND sequence_no > ?
            ORDER BY sequence_no ASC
            """,
            (trace_id, after_sequence),
        )
        return tuple(cast(sqlite3.Row, row) for row in cursor.fetchall())

    def _load_stream(
        self,
        trace_id: TraceId,
    ) -> tuple[EventEnvelope, ...]:
        events: list[EventEnvelope] = []
        for row in self._load_rows(trace_id):
            try:
                event = EventEnvelope.model_validate_json(cast(str, row["envelope_json"]))
            except ValidationError as error:
                sequence_no = cast(int, row["sequence_no"])
                raise _StoredRepresentationError(
                    sequence_no,
                    f"stored envelope at sequence {sequence_no} is invalid",
                ) from error
            indexed_values = (
                row["event_id"],
                row["trace_id"],
                row["sequence_no"],
                row["previous_event_hash"],
                row["event_hash"],
            )
            envelope_values = (
                event.event_id,
                event.trace_id,
                event.sequence_no,
                event.previous_event_hash,
                event.event_hash,
            )
            if indexed_values != envelope_values:
                raise _StoredRepresentationError(
                    event.sequence_no,
                    f"stored indexes disagree with envelope at sequence {event.sequence_no}",
                )
            events.append(event)
        loaded = tuple(events)
        self._validate_stream_index(trace_id, loaded)
        return loaded

    def _validate_stream_index(
        self,
        trace_id: TraceId,
        events: tuple[EventEnvelope, ...],
    ) -> None:
        stream = self._connection.execute(
            """
            SELECT puzzle_revision_id, latest_sequence, latest_event_hash
            FROM event_streams
            WHERE trace_id = ?
            """,
            (trace_id,),
        ).fetchone()
        if stream is None:
            if events:
                raise _StoredRepresentationError(
                    events[0].sequence_no,
                    "stored events have no stream index",
                )
            return
        if not events:
            raise _StoredRepresentationError(0, "stream index has no stored events")

        latest = events[-1]
        indexed_head = (
            stream["puzzle_revision_id"],
            stream["latest_sequence"],
            stream["latest_event_hash"],
        )
        envelope_head = (
            latest.puzzle_revision_id,
            latest.sequence_no,
            latest.event_hash,
        )
        if indexed_head != envelope_head:
            raise _StoredRepresentationError(
                latest.sequence_no,
                f"stream index disagrees with envelope at sequence {latest.sequence_no}",
            )

    def read_stream(
        self,
        trace_id: TraceId,
        *,
        after_sequence: int = -1,
    ) -> tuple[EventEnvelope, ...]:
        """Return an ordered stream after validating stored indexes and envelopes."""
        events = self._load_stream(trace_id)
        verification = verify_chain(events)
        if not verification.valid:
            raise StreamIntegrityError(
                f"stream is invalid at sequence {verification.first_invalid_sequence}"
            )
        return tuple(event for event in events if event.sequence_no > after_sequence)

    def latest(self, trace_id: TraceId) -> EventEnvelope | None:
        """Return the latest verified event without changing stream state."""
        events = self.read_stream(trace_id)
        return events[-1] if events else None

    def verify_stream(self, trace_id: TraceId) -> ChainVerification:
        """Return full-chain verification, including persistent representation checks."""
        rows = self._load_rows(trace_id)
        try:
            events = self._load_stream(trace_id)
        except _StoredRepresentationError as error:
            first_invalid = error.sequence_no
            return ChainVerification(
                total_count=len(rows),
                first_invalid_sequence=first_invalid,
                reason="stored_representation_invalid",
                untrusted_sequences=tuple(
                    cast(int, row["sequence_no"])
                    for row in rows
                    if cast(int, row["sequence_no"]) >= first_invalid
                ),
            )
        return verify_chain(events)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
