"""Behavior and replay evidence for the Logic Grid play-session boundary."""

from __future__ import annotations

import json

import pytest

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.families.logic_grid import (
    HARBOR_MORNING_SOLUTION,
    AssignCell,
    CheckCompletion,
    ClearCell,
    ExcludeCell,
    PlaySessionError,
    PlaySessionStatus,
    RedoMove,
    UndoMove,
    apply_logic_grid_play_action,
    harbor_morning,
    logic_grid_play_session_json_schema,
    rendered_logic_grid_play_session_json_schema,
    replay_logic_grid_play,
    start_logic_grid_play,
)


def _editable_cell() -> tuple[str, str]:
    puzzle = harbor_morning()
    variable_id = puzzle.categories[1].variable_ids[0]
    anchor = next(
        category
        for category in puzzle.categories
        if category.category_id == puzzle.anchor_category_id
    )
    domain = next(item for item in puzzle.domains if item.domain_id == anchor.domain_id)
    return variable_id, domain.values[0].value_id


def test_session_starts_with_only_immutable_givens() -> None:
    puzzle = harbor_morning()

    session = start_logic_grid_play(puzzle, attempt_id="attempt-1")

    assert session.status is PlaySessionStatus.ACTIVE
    assert session.events == ()
    assert session.active_move_id is None
    assert session.assignments == tuple(
        sorted(
            (item for item in puzzle.givens if isinstance(item, AssignmentAtom)),
            key=lambda item: (item.variable_id, item.value_id),
        )
    )


def test_tentative_marks_are_not_reasoning_deductions() -> None:
    puzzle = harbor_morning()
    variable_id, value_id = _editable_cell()
    session = start_logic_grid_play(puzzle, attempt_id="attempt-1")

    assigned = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="move-1",
        action=AssignCell(variable_id=variable_id, value_id=value_id),
    )
    excluded = apply_logic_grid_play_action(
        assigned.session,
        puzzle,
        event_id="move-2",
        action=ExcludeCell(variable_id=variable_id, value_id=value_id),
    )
    cleared = apply_logic_grid_play_action(
        excluded.session,
        puzzle,
        event_id="move-3",
        action=ClearCell(variable_id=variable_id, value_id=value_id),
    )

    assert assigned.accepted
    assert (
        AssignmentAtom(variable_id=variable_id, value_id=value_id) in assigned.session.assignments
    )
    assert ExclusionAtom(variable_id=variable_id, value_id=value_id) in excluded.session.exclusions
    assert not any(item.variable_id == variable_id for item in excluded.session.assignments)
    assert not any(item.variable_id == variable_id for item in cleared.session.assignments)
    assert (
        ExclusionAtom(variable_id=variable_id, value_id=value_id) not in cleared.session.exclusions
    )
    assert tuple(event.action.kind for event in cleared.session.events) == (
        "assign_cell",
        "exclude_cell",
        "clear_cell",
    )


@pytest.mark.parametrize(
    ("action", "code"),
    [
        (AssignCell(variable_id="missing", value_id="missing"), "unknown_variable"),
        (
            AssignCell(
                variable_id=_editable_cell()[0],
                value_id="missing",
            ),
            "unknown_value",
        ),
    ],
)
def test_invalid_cell_references_are_rejected_and_retained(action: AssignCell, code: str) -> None:
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id="attempt-1")

    result = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="rejected-1",
        action=action,
    )

    assert not result.accepted
    assert result.code == code
    assert result.session.assignments == session.assignments
    assert result.session.events[-1].accepted is False
    assert result.session.events[-1].resulting_state_hash == session.state_hash


def test_fixed_givens_cannot_be_changed() -> None:
    puzzle = harbor_morning()
    given = next(item for item in puzzle.givens if isinstance(item, AssignmentAtom))
    session = start_logic_grid_play(puzzle, attempt_id="attempt-1")

    result = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="rejected-1",
        action=ClearCell(variable_id=given.variable_id, value_id=given.value_id),
    )

    assert not result.accepted
    assert result.code == "given_locked"
    assert given in result.session.assignments


def test_undo_redo_and_new_branches_retain_every_move() -> None:
    puzzle = harbor_morning()
    variable_id, first_value = _editable_cell()
    anchor = puzzle.categories[0]
    domain = next(item for item in puzzle.domains if item.domain_id == anchor.domain_id)
    second_value = domain.values[1].value_id
    session = start_logic_grid_play(puzzle, attempt_id="attempt-1")

    first = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="move-1",
        action=AssignCell(variable_id=variable_id, value_id=first_value),
    ).session
    undone = apply_logic_grid_play_action(
        first,
        puzzle,
        event_id="undo-1",
        action=UndoMove(),
    ).session
    redone = apply_logic_grid_play_action(
        undone,
        puzzle,
        event_id="redo-1",
        action=RedoMove(target_move_id="move-1"),
    ).session
    undone_again = apply_logic_grid_play_action(
        redone,
        puzzle,
        event_id="undo-2",
        action=UndoMove(),
    ).session
    branched = apply_logic_grid_play_action(
        undone_again,
        puzzle,
        event_id="move-2",
        action=AssignCell(variable_id=variable_id, value_id=second_value),
    ).session

    assert branched.active_move_id == "move-2"
    assert (
        next(item for item in branched.assignments if item.variable_id == variable_id).value_id
        == second_value
    )
    assert {event.event_id for event in branched.events} == {
        "move-1",
        "undo-1",
        "redo-1",
        "undo-2",
        "move-2",
    }
    unavailable = apply_logic_grid_play_action(
        branched,
        puzzle,
        event_id="redo-2",
        action=RedoMove(target_move_id="move-1"),
    )
    assert not unavailable.accepted
    assert unavailable.code == "redo_target_unavailable"


def test_completion_fails_closed_then_accepts_only_independent_final_check() -> None:
    puzzle = harbor_morning()
    session = start_logic_grid_play(puzzle, attempt_id="attempt-1")

    incomplete = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="check-0",
        action=CheckCompletion(),
    )
    assert not incomplete.accepted
    assert incomplete.session.status is PlaySessionStatus.ACTIVE

    current = incomplete.session
    given_variables = {
        item.variable_id for item in puzzle.givens if isinstance(item, AssignmentAtom)
    }
    for index, assignment in enumerate(
        (item for item in HARBOR_MORNING_SOLUTION if item.variable_id not in given_variables),
        start=1,
    ):
        current = apply_logic_grid_play_action(
            current,
            puzzle,
            event_id=f"solution-{index}",
            action=AssignCell(
                variable_id=assignment.variable_id,
                value_id=assignment.value_id,
            ),
        ).session

    completed = apply_logic_grid_play_action(
        current,
        puzzle,
        event_id="check-1",
        action=CheckCompletion(),
    )
    assert completed.accepted
    assert completed.session.status is PlaySessionStatus.COMPLETED

    closed = apply_logic_grid_play_action(
        completed.session,
        puzzle,
        event_id="closed-1",
        action=UndoMove(),
    )
    assert not closed.accepted
    assert closed.code == "session_closed"


def test_complete_history_replays_exactly_and_tampering_fails() -> None:
    puzzle = harbor_morning()
    variable_id, value_id = _editable_cell()
    session = start_logic_grid_play(puzzle, attempt_id="attempt-1")
    session = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="move-1",
        action=AssignCell(variable_id=variable_id, value_id=value_id),
    ).session
    session = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="undo-1",
        action=UndoMove(),
    ).session

    replayed = replay_logic_grid_play(
        puzzle,
        attempt_id=session.attempt_id,
        events=session.events,
    )
    assert replayed == session

    tampered = session.events[0].model_copy(update={"event_hash": "f" * 64})
    with pytest.raises(PlaySessionError, match="deterministic replay"):
        replay_logic_grid_play(
            puzzle,
            attempt_id=session.attempt_id,
            events=(tampered,),
        )


def test_play_session_schema_is_stable_and_parseable() -> None:
    schema = logic_grid_play_session_json_schema()
    rendered = rendered_logic_grid_play_session_json_schema()

    assert schema["$id"] == "urn:deductra:schema:logic-grid-play-session:1"
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert json.loads(rendered) == schema
    assert rendered.endswith("\n")
