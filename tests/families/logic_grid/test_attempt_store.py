"""Persistence, replay, and evidence tests for Logic Grid attempts."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from deductra.domain.atoms import AssignmentAtom
from deductra.families.logic_grid import (
    HARBOR_MORNING_SOLUTION,
    AssignCell,
    AttemptAlreadyExistsError,
    AttemptConflictError,
    AttemptIntegrityError,
    CheckCompletion,
    LogicGridAttemptStore,
    LogicGridPlaySession,
    LogicGridSpec,
    SQLiteLogicGridAttemptStore,
    apply_logic_grid_play_action,
    gallery_opening,
    harbor_morning,
    logic_grid_attempt_record_json_schema,
    rendered_logic_grid_attempt_record_json_schema,
    replay_logic_grid_play,
    start_logic_grid_play,
)
from deductra.memory.projections import AttemptStatus, rebuild_memory_projections

STARTED_AT = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
USER_ID = "deductra:user:local-test"
ATTEMPT_ID = "deductra:attempt:logic-grid:persistence-test"


def _first_editable_assignment() -> AssignCell:
    puzzle = harbor_morning()
    variable_id = puzzle.categories[1].variable_ids[0]
    anchor = next(
        category
        for category in puzzle.categories
        if category.category_id == puzzle.anchor_category_id
    )
    domain = next(item for item in puzzle.domains if item.domain_id == anchor.domain_id)
    return AssignCell(variable_id=variable_id, value_id=domain.values[0].value_id)


def _completed_session() -> tuple[LogicGridSpec, LogicGridPlaySession]:
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id=ATTEMPT_ID)
    given_variables = {
        item.variable_id for item in puzzle.givens if isinstance(item, AssignmentAtom)
    }
    for index, assignment in enumerate(
        (item for item in HARBOR_MORNING_SOLUTION if item.variable_id not in given_variables),
        start=1,
    ):
        session = apply_logic_grid_play_action(
            session,
            puzzle,
            event_id=f"solution-{index}",
            action=AssignCell(
                variable_id=assignment.variable_id,
                value_id=assignment.value_id,
            ),
        ).session
    session = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="completion",
        action=CheckCompletion(),
    ).session
    return puzzle, session


def test_store_round_trips_exact_play_history_and_descriptive_evidence(tmp_path: Path) -> None:
    database = tmp_path / "attempts.sqlite3"
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id=ATTEMPT_ID)

    with SQLiteLogicGridAttemptStore(database) as store:
        assert isinstance(store, LogicGridAttemptStore)
        created = store.create(
            puzzle,
            session,
            user_id=USER_ID,
            occurred_at=STARTED_AT,
        )
        assert created.session == session
        assert created.evidence.total_actions == 0
        assert created.attempt_projection.status is AttemptStatus.ACTIVE
        assert tuple(item.payload.kind for item in created.projection_events) == (
            "attempt_started",
        )

        changed = apply_logic_grid_play_action(
            session,
            puzzle,
            event_id="move-1",
            action=_first_editable_assignment(),
        ).session
        appended = store.append(
            puzzle,
            changed,
            occurred_at=STARTED_AT + timedelta(seconds=1),
        )
        assert appended.evidence.total_actions == 1
        assert appended.evidence.accepted_actions == 1
        assert appended.evidence.action_evidence[0].kind == "assign_cell"
        assert appended.attempt_projection.total_moves == 0
        assert store.read(puzzle, ATTEMPT_ID) == appended

    with SQLiteLogicGridAttemptStore(database) as reopened:
        assert reopened.read(puzzle, ATTEMPT_ID) == appended


def test_verified_completion_is_the_only_play_fact_normalized_as_memory_authority(
    tmp_path: Path,
) -> None:
    database = tmp_path / "attempts.sqlite3"
    puzzle, session = _completed_session()

    with SQLiteLogicGridAttemptStore(database) as store:
        current = start_logic_grid_play(puzzle, attempt_id=ATTEMPT_ID)
        record = store.create(
            puzzle,
            current,
            user_id=USER_ID,
            occurred_at=STARTED_AT,
        )
        for index in range(len(session.events)):
            current = replay_logic_grid_play(
                puzzle,
                attempt_id=ATTEMPT_ID,
                validation_mode=session.validation_mode,
                events=session.events[: index + 1],
            )
            record = store.append(
                puzzle,
                current,
                occurred_at=STARTED_AT + timedelta(seconds=index + 1),
            )

    assert record.attempt_projection.status is AttemptStatus.COMPLETED
    assert record.attempt_projection.total_moves == 0
    assert tuple(item.payload.kind for item in record.projection_events) == (
        "attempt_started",
        "attempt_completed",
    )
    rebuilt = rebuild_memory_projections(record.projection_events)
    assert rebuilt.attempts == (record.attempt_projection,)
    assert rebuilt.learning[0].completed_attempts == 1
    assert rebuilt.learning[0].rule_evidence == ()


def test_duplicate_create_and_stale_append_fail_without_partial_history(tmp_path: Path) -> None:
    database = tmp_path / "attempts.sqlite3"
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id=ATTEMPT_ID)
    first_branch = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="move-first",
        action=_first_editable_assignment(),
    ).session
    competing_branch = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="move-competing",
        action=_first_editable_assignment(),
    ).session

    with SQLiteLogicGridAttemptStore(database) as first:
        first.create(puzzle, session, user_id=USER_ID, occurred_at=STARTED_AT)
        with pytest.raises(AttemptAlreadyExistsError):
            first.create(puzzle, session, user_id=USER_ID, occurred_at=STARTED_AT)
        with SQLiteLogicGridAttemptStore(database) as second:
            first.append(
                puzzle,
                first_branch,
                occurred_at=STARTED_AT + timedelta(seconds=1),
            )
            with pytest.raises(AttemptConflictError):
                second.append(
                    puzzle,
                    competing_branch,
                    occurred_at=STARTED_AT + timedelta(seconds=2),
                )
            stored = second.read(puzzle, ATTEMPT_ID)
            assert stored is not None
            assert tuple(item.event.event_id for item in stored.observations) == ("move-first",)


def test_append_rejects_missing_stream_and_backwards_observation_time(tmp_path: Path) -> None:
    database = tmp_path / "attempts.sqlite3"
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id=ATTEMPT_ID)
    changed = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="move-1",
        action=_first_editable_assignment(),
    ).session

    with SQLiteLogicGridAttemptStore(database) as store:
        with pytest.raises(AttemptConflictError):
            store.append(puzzle, changed, occurred_at=STARTED_AT)
        store.create(puzzle, session, user_id=USER_ID, occurred_at=STARTED_AT)
        with pytest.raises(AttemptConflictError):
            store.append(
                puzzle,
                changed,
                occurred_at=STARTED_AT - timedelta(microseconds=1),
            )
        stored = store.read(puzzle, ATTEMPT_ID)
        assert stored is not None
        assert stored.observations == ()


@pytest.mark.parametrize(
    ("statement", "parameters"),
    [
        (
            "UPDATE logic_grid_attempt_streams SET latest_event_hash = ? WHERE attempt_id = ?",
            ("f" * 64, ATTEMPT_ID),
        ),
        (
            "UPDATE logic_grid_attempt_streams SET record_json = ? WHERE attempt_id = ?",
            ("{}", ATTEMPT_ID),
        ),
        (
            "UPDATE logic_grid_attempt_events SET observation_json = ? WHERE attempt_id = ?",
            ("{}", ATTEMPT_ID),
        ),
    ],
)
def test_persistent_tampering_fails_closed(
    tmp_path: Path,
    statement: str,
    parameters: tuple[str, str],
) -> None:
    database = tmp_path / "attempts.sqlite3"
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id=ATTEMPT_ID)
    changed = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="move-1",
        action=_first_editable_assignment(),
    ).session
    with SQLiteLogicGridAttemptStore(database) as store:
        store.create(puzzle, session, user_id=USER_ID, occurred_at=STARTED_AT)
        store.append(
            puzzle,
            changed,
            occurred_at=STARTED_AT + timedelta(seconds=1),
        )

    with closing(sqlite3.connect(database)) as connection:
        connection.execute(statement, parameters)
        connection.commit()

    with (
        SQLiteLogicGridAttemptStore(database) as store,
        pytest.raises(AttemptIntegrityError),
    ):
        store.read(puzzle, ATTEMPT_ID)


def test_wrong_puzzle_revision_cannot_replay_stored_attempt(tmp_path: Path) -> None:
    database = tmp_path / "attempts.sqlite3"
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id=ATTEMPT_ID)
    with SQLiteLogicGridAttemptStore(database) as store:
        store.create(puzzle, session, user_id=USER_ID, occurred_at=STARTED_AT)
        with pytest.raises(AttemptIntegrityError):
            store.read(gallery_opening(), ATTEMPT_ID)


def test_attempt_record_schema_is_checked_in_and_strict() -> None:
    schema = logic_grid_attempt_record_json_schema()
    checked_in = Path("schemas/logic-grid-attempt-record-v1.schema.json").read_text(
        encoding="utf-8"
    )

    assert schema["$id"] == "urn:deductra:schema:logic-grid-attempt-record:1"
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert schema["additionalProperties"] is False
    assert json.loads(checked_in) == schema
    assert checked_in == rendered_logic_grid_attempt_record_json_schema()
