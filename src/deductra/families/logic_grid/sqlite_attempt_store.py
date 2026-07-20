"""Transactional SQLite adapter for local Logic Grid attempt history."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from pydantic import ValidationError

from deductra.domain.ids import AttemptId, UserId
from deductra.domain.serialization import canonical_json
from deductra.families.logic_grid.attempts import (
    ATTEMPT_RECORD_SCHEMA_VERSION,
    AttemptAlreadyExistsError,
    AttemptConflictError,
    AttemptIntegrityError,
    ObservedPlayEvent,
    PersistedLogicGridAttempt,
    build_persisted_logic_grid_attempt,
    observe_play_event,
)
from deductra.families.logic_grid.play import (
    PLAY_GENESIS_HASH,
    LogicGridPlaySession,
    PlayValidationMode,
    replay_logic_grid_play,
)
from deductra.families.logic_grid.specification import LogicGridSpec

SQLITE_ATTEMPT_SCHEMA_VERSION = 1
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS logic_grid_attempt_streams (
    attempt_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    puzzle_revision_id TEXT NOT NULL,
    validation_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    latest_sequence INTEGER NOT NULL CHECK (latest_sequence >= -1),
    latest_event_hash TEXT NOT NULL CHECK (length(latest_event_hash) = 64),
    session_hash TEXT NOT NULL CHECK (length(session_hash) = 64),
    record_hash TEXT NOT NULL CHECK (length(record_hash) = 64),
    record_json TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS logic_grid_attempt_events (
    event_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES logic_grid_attempt_streams(attempt_id),
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    occurred_at TEXT NOT NULL,
    previous_event_hash TEXT NOT NULL CHECK (length(previous_event_hash) = 64),
    event_hash TEXT NOT NULL UNIQUE CHECK (length(event_hash) = 64),
    observation_hash TEXT NOT NULL UNIQUE CHECK (length(observation_hash) = 64),
    observation_json TEXT NOT NULL,
    UNIQUE (attempt_id, sequence_no)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_logic_grid_attempt_events_stream_sequence
ON logic_grid_attempt_events(attempt_id, sequence_no);

CREATE TABLE IF NOT EXISTS logic_grid_attempt_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
) STRICT;
"""


class SQLiteLogicGridAttemptStore:
    """Single-connection, append-only local attempt store."""

    def __init__(self, database: str | Path) -> None:
        self._connection = sqlite3.connect(database, autocommit=True)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        if str(database) != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        self._connection.executescript(SCHEMA_SQL)
        self._connection.execute(
            """
            INSERT OR IGNORE INTO logic_grid_attempt_schema_migrations(version, applied_at)
            VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (SQLITE_ATTEMPT_SCHEMA_VERSION,),
        )

    def create(
        self,
        puzzle: LogicGridSpec,
        session: LogicGridPlaySession,
        *,
        user_id: UserId,
        occurred_at: datetime,
    ) -> PersistedLogicGridAttempt:
        """Create an empty stream and its initial lifecycle projection atomically."""
        if session.events:
            raise AttemptConflictError("a new attempt stream must not contain play events")
        replayed = replay_logic_grid_play(
            puzzle,
            attempt_id=session.attempt_id,
            validation_mode=session.validation_mode,
            events=(),
        )
        if replayed != session:
            raise AttemptIntegrityError("new attempt does not equal its canonical empty replay")
        record = build_persisted_logic_grid_attempt(
            session,
            user_id=user_id,
            started_at=occurred_at,
            observations=(),
        )

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self._connection.execute(
                "SELECT 1 FROM logic_grid_attempt_streams WHERE attempt_id = ?",
                (session.attempt_id,),
            ).fetchone()
            if existing is not None:
                raise AttemptAlreadyExistsError("attempt identifier already exists")
            self._insert_stream(record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise AttemptAlreadyExistsError("attempt identifier already exists") from error
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        return record

    def append(
        self,
        puzzle: LogicGridSpec,
        session: LogicGridPlaySession,
        *,
        occurred_at: datetime,
    ) -> PersistedLogicGridAttempt:
        """Atomically append exactly one observed play event and replace derived views."""
        replayed = replay_logic_grid_play(
            puzzle,
            attempt_id=session.attempt_id,
            validation_mode=session.validation_mode,
            events=session.events,
        )
        if replayed != session:
            raise AttemptIntegrityError("supplied attempt does not equal its canonical replay")

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            current = self._read_verified(puzzle, session.attempt_id)
            if current is None:
                raise AttemptConflictError("attempt stream does not exist")
            if len(session.events) != len(current.session.events) + 1:
                raise AttemptConflictError("append must continue the stream by exactly one event")
            if session.events[:-1] != current.session.events:
                raise AttemptConflictError("append does not continue the durable stream head")
            if occurred_at < current.updated_at:
                raise AttemptConflictError("event observation time cannot move backwards")

            observation = observe_play_event(session.events[-1], occurred_at=occurred_at)
            observations = (*current.observations, observation)
            record = build_persisted_logic_grid_attempt(
                session,
                user_id=current.user_id,
                started_at=current.started_at,
                observations=observations,
            )
            self._insert_observation(session.attempt_id, observation)
            self._update_stream(record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise AttemptConflictError(
                "event identifier or attempt sequence already exists"
            ) from error
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        return record

    def _insert_stream(self, record: PersistedLogicGridAttempt) -> None:
        session = record.session
        self._connection.execute(
            """
            INSERT INTO logic_grid_attempt_streams(
                attempt_id,
                user_id,
                puzzle_revision_id,
                validation_mode,
                status,
                started_at,
                updated_at,
                latest_sequence,
                latest_event_hash,
                session_hash,
                record_hash,
                record_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.attempt_id,
                record.user_id,
                session.puzzle_revision_id,
                session.validation_mode.value,
                session.status.value,
                record.started_at.isoformat(),
                record.updated_at.isoformat(),
                -1,
                PLAY_GENESIS_HASH,
                session.session_hash,
                record.record_hash,
                canonical_json(record),
            ),
        )

    def _insert_observation(
        self,
        attempt_id: AttemptId,
        observation: ObservedPlayEvent,
    ) -> None:
        event = observation.event
        self._connection.execute(
            """
            INSERT INTO logic_grid_attempt_events(
                event_id,
                attempt_id,
                sequence_no,
                occurred_at,
                previous_event_hash,
                event_hash,
                observation_hash,
                observation_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                attempt_id,
                event.sequence_no,
                observation.occurred_at.isoformat(),
                event.previous_event_hash,
                event.event_hash,
                observation.observation_hash,
                canonical_json(observation),
            ),
        )

    def _update_stream(self, record: PersistedLogicGridAttempt) -> None:
        session = record.session
        event = session.events[-1]
        updated = self._connection.execute(
            """
            UPDATE logic_grid_attempt_streams
            SET
                status = ?,
                updated_at = ?,
                latest_sequence = ?,
                latest_event_hash = ?,
                session_hash = ?,
                record_hash = ?,
                record_json = ?
            WHERE attempt_id = ?
            """,
            (
                session.status.value,
                record.updated_at.isoformat(),
                event.sequence_no,
                event.event_hash,
                session.session_hash,
                record.record_hash,
                canonical_json(record),
                session.attempt_id,
            ),
        )
        if updated.rowcount != 1:
            raise AttemptConflictError("attempt stream disappeared during append")

    def _load_observations(self, attempt_id: AttemptId) -> tuple[ObservedPlayEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT
                event_id,
                sequence_no,
                occurred_at,
                previous_event_hash,
                event_hash,
                observation_hash,
                observation_json
            FROM logic_grid_attempt_events
            WHERE attempt_id = ?
            ORDER BY sequence_no ASC
            """,
            (attempt_id,),
        ).fetchall()
        observations: list[ObservedPlayEvent] = []
        for row_value in rows:
            row = cast(sqlite3.Row, row_value)
            try:
                observation = ObservedPlayEvent.model_validate_json(
                    cast(str, row["observation_json"])
                )
            except ValidationError as error:
                raise AttemptIntegrityError("stored play observation is invalid") from error
            event = observation.event
            indexed = (
                row["event_id"],
                row["sequence_no"],
                row["occurred_at"],
                row["previous_event_hash"],
                row["event_hash"],
                row["observation_hash"],
            )
            represented = (
                event.event_id,
                event.sequence_no,
                observation.occurred_at.isoformat(),
                event.previous_event_hash,
                event.event_hash,
                observation.observation_hash,
            )
            if indexed != represented:
                raise AttemptIntegrityError("stored indexes disagree with a play observation")
            observations.append(observation)
        return tuple(observations)

    def _read_verified(
        self,
        puzzle: LogicGridSpec,
        attempt_id: AttemptId,
    ) -> PersistedLogicGridAttempt | None:
        stream_value = self._connection.execute(
            "SELECT * FROM logic_grid_attempt_streams WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if stream_value is None:
            return None
        stream = cast(sqlite3.Row, stream_value)
        observations = self._load_observations(attempt_id)
        events = tuple(item.event for item in observations)
        try:
            session = replay_logic_grid_play(
                puzzle,
                attempt_id=attempt_id,
                validation_mode=PlayValidationMode(cast(str, stream["validation_mode"])),
                events=events,
            )
        except (ValidationError, ValueError) as error:
            raise AttemptIntegrityError("stored play history cannot be replayed") from error
        try:
            started_at = datetime.fromisoformat(cast(str, stream["started_at"]))
            record = build_persisted_logic_grid_attempt(
                session,
                user_id=cast(str, stream["user_id"]),
                started_at=started_at,
                observations=observations,
            )
            stored_record = PersistedLogicGridAttempt.model_validate_json(
                cast(str, stream["record_json"])
            )
        except (ValidationError, ValueError) as error:
            raise AttemptIntegrityError("stored attempt projection is invalid") from error

        latest_sequence = events[-1].sequence_no if events else -1
        latest_hash = events[-1].event_hash if events else PLAY_GENESIS_HASH
        indexed = (
            stream["user_id"],
            stream["puzzle_revision_id"],
            stream["validation_mode"],
            stream["status"],
            stream["started_at"],
            stream["updated_at"],
            stream["latest_sequence"],
            stream["latest_event_hash"],
            stream["session_hash"],
            stream["record_hash"],
        )
        represented = (
            record.user_id,
            session.puzzle_revision_id,
            session.validation_mode.value,
            session.status.value,
            record.started_at.isoformat(),
            record.updated_at.isoformat(),
            latest_sequence,
            latest_hash,
            session.session_hash,
            record.record_hash,
        )
        if indexed != represented or stored_record != record:
            raise AttemptIntegrityError("stored stream index or projection disagrees with replay")
        if record.schema_version != ATTEMPT_RECORD_SCHEMA_VERSION:
            raise AttemptIntegrityError("stored attempt schema version is unsupported")
        return record

    def read(
        self,
        puzzle: LogicGridSpec,
        attempt_id: AttemptId,
    ) -> PersistedLogicGridAttempt | None:
        """Return one attempt only after replay and projection equivalence checks."""
        return self._read_verified(puzzle, attempt_id)

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
