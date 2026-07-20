"""Immutable, replayable Logic Grid play-session application service."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.base import DomainModel
from deductra.domain.ids import AttemptId, EventId, PuzzleRevisionId, ValueId, VariableId
from deductra.domain.serialization import canonical_sha256
from deductra.families.logic_grid.checker import check_logic_grid_solution
from deductra.families.logic_grid.specification import LogicGridSpec

PLAY_SCHEMA_VERSION = "1.0.0"
PLAY_GENESIS_HASH = "0" * 64
MAX_PLAY_EVENTS = 10_000
type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PlaySessionStatus(StrEnum):
    """Terminal status of a presentation-neutral play attempt."""

    ACTIVE = "active"
    COMPLETED = "completed"


class AssignCell(DomainModel):
    """Tentatively select one anchor row for an item variable."""

    kind: Literal["assign_cell"] = "assign_cell"
    variable_id: VariableId
    value_id: ValueId


class ExcludeCell(DomainModel):
    """Tentatively exclude one anchor row from an item variable."""

    kind: Literal["exclude_cell"] = "exclude_cell"
    variable_id: VariableId
    value_id: ValueId


class ClearCell(DomainModel):
    """Clear a tentative selection or exclusion from one cell."""

    kind: Literal["clear_cell"] = "clear_cell"
    variable_id: VariableId
    value_id: ValueId


class UndoMove(DomainModel):
    """Move the active history cursor to the parent of its current move."""

    kind: Literal["undo_move"] = "undo_move"


class RedoMove(DomainModel):
    """Move the active history cursor to one retained direct child."""

    kind: Literal["redo_move"] = "redo_move"
    target_move_id: EventId


class CheckCompletion(DomainModel):
    """Ask the independent final checker to evaluate the active marks."""

    kind: Literal["check_completion"] = "check_completion"


type PlayAction = Annotated[
    AssignCell | ExcludeCell | ClearCell | UndoMove | RedoMove | CheckCompletion,
    Field(discriminator="kind"),
]
type CellAction = AssignCell | ExcludeCell | ClearCell


class PlayEvent(DomainModel):
    """One retained interaction outcome in a tamper-evident attempt stream."""

    event_id: EventId
    sequence_no: Annotated[int, Field(ge=0)]
    schema_version: Literal["1.0.0"] = PLAY_SCHEMA_VERSION
    action: PlayAction
    accepted: bool
    code: str
    message: str
    parent_move_id: EventId | None = None
    resulting_move_id: EventId | None = None
    resulting_state_hash: Sha256Digest
    previous_event_hash: Sha256Digest
    event_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_event(self) -> PlayEvent:
        if not self.code or not self.message:
            raise ValueError("play outcomes require a code and message")
        if self.event_hash != compute_play_event_hash(self):
            raise ValueError("event_hash does not match the canonical play event")
        return self


class LogicGridPlaySession(DomainModel):
    """Current immutable marks plus the complete retained interaction history."""

    schema_version: Literal["1.0.0"] = PLAY_SCHEMA_VERSION
    attempt_id: AttemptId
    puzzle_revision_id: PuzzleRevisionId
    status: PlaySessionStatus
    assignments: tuple[AssignmentAtom, ...]
    exclusions: tuple[ExclusionAtom, ...]
    active_move_id: EventId | None = None
    events: Annotated[tuple[PlayEvent, ...], Field(max_length=MAX_PLAY_EVENTS)] = ()
    state_hash: Sha256Digest
    session_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_session_shape(self) -> LogicGridPlaySession:
        assignment_keys = tuple((item.variable_id, item.value_id) for item in self.assignments)
        exclusion_keys = tuple((item.variable_id, item.value_id) for item in self.exclusions)
        if assignment_keys != tuple(sorted(assignment_keys)):
            raise ValueError("assignments must use canonical order")
        if exclusion_keys != tuple(sorted(exclusion_keys)):
            raise ValueError("exclusions must use canonical order")
        if len({item.variable_id for item in self.assignments}) != len(self.assignments):
            raise ValueError("a play session cannot assign one variable more than once")
        if set(assignment_keys) & set(exclusion_keys):
            raise ValueError("a cell cannot be both assigned and excluded")
        if self.state_hash != compute_play_state_hash(self):
            raise ValueError("state_hash does not match the current play state")
        if self.session_hash != compute_play_session_hash(self):
            raise ValueError("session_hash does not match the canonical play session")
        return self


class PlayActionResult(DomainModel):
    """Presentation-safe outcome and the resulting immutable session."""

    accepted: bool
    code: str
    message: str
    session: LogicGridPlaySession


class PlaySessionError(ValueError):
    """A supplied session or event stream cannot be trusted or replayed."""


def compute_play_event_hash(event: PlayEvent) -> str:
    """Hash every canonical event field except the digest itself."""
    return canonical_sha256(event.model_dump(mode="json", exclude={"event_hash"}))


def compute_play_state_hash(session: LogicGridPlaySession) -> str:
    """Hash the active interaction state without its retained history."""
    return canonical_sha256(
        {
            "attempt_id": session.attempt_id,
            "puzzle_revision_id": session.puzzle_revision_id,
            "status": session.status,
            "assignments": session.assignments,
            "exclusions": session.exclusions,
            "active_move_id": session.active_move_id,
        }
    )


def compute_play_session_hash(session: LogicGridPlaySession) -> str:
    """Hash the entire play session, including retained inactive branches."""
    return canonical_sha256(session.model_dump(mode="json", exclude={"session_hash"}))


def _build_session(
    *,
    attempt_id: AttemptId,
    puzzle_revision_id: PuzzleRevisionId,
    status: PlaySessionStatus,
    assignments: dict[VariableId, ValueId],
    exclusions: set[tuple[VariableId, ValueId]],
    active_move_id: EventId | None,
    events: tuple[PlayEvent, ...],
) -> LogicGridPlaySession:
    ordered_assignments = tuple(
        AssignmentAtom(variable_id=variable_id, value_id=value_id)
        for variable_id, value_id in sorted(assignments.items())
    )
    ordered_exclusions = tuple(
        ExclusionAtom(variable_id=variable_id, value_id=value_id)
        for variable_id, value_id in sorted(exclusions)
    )
    unsigned = LogicGridPlaySession.model_construct(
        schema_version=PLAY_SCHEMA_VERSION,
        attempt_id=attempt_id,
        puzzle_revision_id=puzzle_revision_id,
        status=status,
        assignments=ordered_assignments,
        exclusions=ordered_exclusions,
        active_move_id=active_move_id,
        events=events,
        state_hash=PLAY_GENESIS_HASH,
        session_hash=PLAY_GENESIS_HASH,
    )
    state_hash = compute_play_state_hash(unsigned)
    with_state = unsigned.model_copy(update={"state_hash": state_hash})
    return LogicGridPlaySession(
        **with_state.model_dump(mode="python", exclude={"session_hash"}),
        session_hash=compute_play_session_hash(with_state),
    )


def start_logic_grid_play(
    puzzle: LogicGridSpec,
    *,
    attempt_id: AttemptId,
) -> LogicGridPlaySession:
    """Start an empty immutable session containing only fixed puzzle givens."""
    assignments = {
        item.variable_id: item.value_id
        for item in puzzle.givens
        if isinstance(item, AssignmentAtom)
    }
    exclusions = {
        (item.variable_id, item.value_id)
        for item in puzzle.givens
        if isinstance(item, ExclusionAtom)
    }
    return _build_session(
        attempt_id=attempt_id,
        puzzle_revision_id=puzzle.identity.revision_id,
        status=PlaySessionStatus.ACTIVE,
        assignments=assignments,
        exclusions=exclusions,
        active_move_id=None,
        events=(),
    )


def _seal_event(
    *,
    event_id: EventId,
    sequence_no: int,
    action: PlayAction,
    accepted: bool,
    code: str,
    message: str,
    parent_move_id: EventId | None,
    resulting_move_id: EventId | None,
    resulting_state_hash: str,
    previous_event_hash: str,
) -> PlayEvent:
    unsigned = PlayEvent.model_construct(
        event_id=event_id,
        sequence_no=sequence_no,
        schema_version=PLAY_SCHEMA_VERSION,
        action=action,
        accepted=accepted,
        code=code,
        message=message,
        parent_move_id=parent_move_id,
        resulting_move_id=resulting_move_id,
        resulting_state_hash=resulting_state_hash,
        previous_event_hash=previous_event_hash,
        event_hash=PLAY_GENESIS_HASH,
    )
    return PlayEvent(
        **unsigned.model_dump(mode="python", exclude={"event_hash"}),
        event_hash=compute_play_event_hash(unsigned),
    )


def _move_events(events: tuple[PlayEvent, ...]) -> dict[EventId, PlayEvent]:
    return {
        event.event_id: event
        for event in events
        if event.accepted and isinstance(event.action, (AssignCell, ExcludeCell, ClearCell))
    }


def _active_path(
    moves: dict[EventId, PlayEvent], active_move_id: EventId | None
) -> tuple[PlayEvent, ...]:
    path: list[PlayEvent] = []
    seen: set[EventId] = set()
    current = active_move_id
    while current is not None:
        if current in seen or current not in moves:
            raise PlaySessionError("active move history is missing or cyclic")
        seen.add(current)
        event = moves[current]
        path.append(event)
        current = event.parent_move_id
    return tuple(reversed(path))


def _apply_cell_action(
    assignments: dict[VariableId, ValueId],
    exclusions: set[tuple[VariableId, ValueId]],
    action: CellAction,
) -> None:
    cell = (action.variable_id, action.value_id)
    if isinstance(action, AssignCell):
        assignments[action.variable_id] = action.value_id
        exclusions.discard(cell)
    elif isinstance(action, ExcludeCell):
        if assignments.get(action.variable_id) == action.value_id:
            assignments.pop(action.variable_id)
        exclusions.add(cell)
    else:
        if assignments.get(action.variable_id) == action.value_id:
            assignments.pop(action.variable_id)
        exclusions.discard(cell)


def _project_marks(
    puzzle: LogicGridSpec,
    moves: dict[EventId, PlayEvent],
    active_move_id: EventId | None,
) -> tuple[dict[VariableId, ValueId], set[tuple[VariableId, ValueId]]]:
    assignments = {
        item.variable_id: item.value_id
        for item in puzzle.givens
        if isinstance(item, AssignmentAtom)
    }
    exclusions = {
        (item.variable_id, item.value_id)
        for item in puzzle.givens
        if isinstance(item, ExclusionAtom)
    }
    for event in _active_path(moves, active_move_id):
        if not isinstance(event.action, (AssignCell, ExcludeCell, ClearCell)):
            raise PlaySessionError("move history contains a non-cell action")
        _apply_cell_action(assignments, exclusions, event.action)
    return assignments, exclusions


def _cell_rejection(puzzle: LogicGridSpec, action: CellAction) -> tuple[str, str] | None:
    variables = {item.variable_id for item in puzzle.variables}
    anchor_category = next(
        item for item in puzzle.categories if item.category_id == puzzle.anchor_category_id
    )
    anchor_domain = next(
        item for item in puzzle.domains if item.domain_id == anchor_category.domain_id
    )
    values = {item.value_id for item in anchor_domain.values}
    if action.variable_id not in variables:
        return "unknown_variable", "That puzzle item is not available."
    if action.value_id not in values:
        return "unknown_value", "That row value is not available."
    assigned_givens = {
        item.variable_id: item.value_id
        for item in puzzle.givens
        if isinstance(item, AssignmentAtom)
    }
    if action.variable_id in assigned_givens:
        return "given_locked", "A fixed puzzle cell cannot be changed."
    excluded_givens = {
        (item.variable_id, item.value_id)
        for item in puzzle.givens
        if isinstance(item, ExclusionAtom)
    }
    if (action.variable_id, action.value_id) in excluded_givens:
        return "given_locked", "A fixed puzzle cell cannot be changed."
    return None


def _append_outcome(
    session: LogicGridPlaySession,
    *,
    event_id: EventId,
    action: PlayAction,
    accepted: bool,
    code: str,
    message: str,
    parent_move_id: EventId | None,
    resulting_move_id: EventId | None,
    status: PlaySessionStatus,
    assignments: dict[VariableId, ValueId],
    exclusions: set[tuple[VariableId, ValueId]],
) -> PlayActionResult:
    provisional = _build_session(
        attempt_id=session.attempt_id,
        puzzle_revision_id=session.puzzle_revision_id,
        status=status,
        assignments=assignments,
        exclusions=exclusions,
        active_move_id=resulting_move_id,
        events=session.events,
    )
    event = _seal_event(
        event_id=event_id,
        sequence_no=len(session.events),
        action=action,
        accepted=accepted,
        code=code,
        message=message,
        parent_move_id=parent_move_id,
        resulting_move_id=resulting_move_id,
        resulting_state_hash=provisional.state_hash,
        previous_event_hash=session.events[-1].event_hash if session.events else PLAY_GENESIS_HASH,
    )
    result = _build_session(
        attempt_id=session.attempt_id,
        puzzle_revision_id=session.puzzle_revision_id,
        status=status,
        assignments=assignments,
        exclusions=exclusions,
        active_move_id=resulting_move_id,
        events=(*session.events, event),
    )
    return PlayActionResult(accepted=accepted, code=code, message=message, session=result)


def _apply_logic_grid_play_action(
    session: LogicGridPlaySession,
    puzzle: LogicGridSpec,
    *,
    event_id: EventId,
    action: PlayAction,
    verify_session: bool,
) -> PlayActionResult:
    if session.puzzle_revision_id != puzzle.identity.revision_id:
        raise PlaySessionError("session puzzle revision does not match the supplied puzzle")
    if event_id in {event.event_id for event in session.events}:
        raise PlaySessionError("play event identifiers must be unique")
    if len(session.events) >= MAX_PLAY_EVENTS:
        raise PlaySessionError("play session event limit reached")
    if verify_session:
        replayed = replay_logic_grid_play(
            puzzle,
            attempt_id=session.attempt_id,
            events=session.events,
        )
        if replayed != session:
            raise PlaySessionError("session does not equal its canonical replay")

    assignments = {item.variable_id: item.value_id for item in session.assignments}
    exclusions = {(item.variable_id, item.value_id) for item in session.exclusions}
    head = session.active_move_id
    moves = _move_events(session.events)
    if session.status is not PlaySessionStatus.ACTIVE:
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=False,
            code="session_closed",
            message="This completed attempt cannot be changed.",
            parent_move_id=head,
            resulting_move_id=head,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
        )

    if isinstance(action, (AssignCell, ExcludeCell, ClearCell)):
        rejection = _cell_rejection(puzzle, action)
        if rejection is not None:
            code, message = rejection
            return _append_outcome(
                session,
                event_id=event_id,
                action=action,
                accepted=False,
                code=code,
                message=message,
                parent_move_id=head,
                resulting_move_id=head,
                status=session.status,
                assignments=assignments,
                exclusions=exclusions,
            )
        _apply_cell_action(assignments, exclusions, action)
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=True,
            code="move_applied",
            message="The tentative mark was applied.",
            parent_move_id=head,
            resulting_move_id=event_id,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
        )

    if isinstance(action, UndoMove):
        if head is None:
            accepted, code, message, target = (
                False,
                "nothing_to_undo",
                "There is no active move to undo.",
                head,
            )
        else:
            accepted, code, message, target = (
                True,
                "move_undone",
                "The active move was undone without deleting history.",
                moves[head].parent_move_id,
            )
        assignments, exclusions = _project_marks(puzzle, moves, target)
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=accepted,
            code=code,
            message=message,
            parent_move_id=head,
            resulting_move_id=target,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
        )

    if isinstance(action, RedoMove):
        target_event = moves.get(action.target_move_id)
        accepted = target_event is not None and target_event.parent_move_id == head
        target = action.target_move_id if accepted else head
        code = "move_redone" if accepted else "redo_target_unavailable"
        message = (
            "The retained move was restored."
            if accepted
            else "Choose a retained move directly after the current history position."
        )
        assignments, exclusions = _project_marks(puzzle, moves, target)
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=accepted,
            code=code,
            message=message,
            parent_move_id=head,
            resulting_move_id=target,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
        )

    check = check_logic_grid_solution(
        puzzle,
        tuple(
            AssignmentAtom(variable_id=variable_id, value_id=value_id)
            for variable_id, value_id in sorted(assignments.items())
        ),
    )
    accepted = check.accepted
    code = "completed" if accepted else "completion_rejected"
    message = (
        "The puzzle is complete and independently verified."
        if accepted
        else "The current selections do not yet form a valid complete solution."
    )
    return _append_outcome(
        session,
        event_id=event_id,
        action=action,
        accepted=accepted,
        code=code,
        message=message,
        parent_move_id=head,
        resulting_move_id=head,
        status=PlaySessionStatus.COMPLETED if accepted else session.status,
        assignments=assignments,
        exclusions=exclusions,
    )


def apply_logic_grid_play_action(
    session: LogicGridPlaySession,
    puzzle: LogicGridSpec,
    *,
    event_id: EventId,
    action: PlayAction,
) -> PlayActionResult:
    """Apply one action, retaining accepted, rejected, undone, and branched history."""
    return _apply_logic_grid_play_action(
        session,
        puzzle,
        event_id=event_id,
        action=action,
        verify_session=True,
    )


def replay_logic_grid_play(
    puzzle: LogicGridSpec,
    *,
    attempt_id: AttemptId,
    events: tuple[PlayEvent, ...],
) -> LogicGridPlaySession:
    """Rebuild an attempt and reject any non-canonical or tampered event stream."""
    session = start_logic_grid_play(puzzle, attempt_id=attempt_id)
    for source in events:
        if source.sequence_no != len(session.events):
            raise PlaySessionError("play event sequence is not contiguous")
        expected_previous = session.events[-1].event_hash if session.events else PLAY_GENESIS_HASH
        if source.previous_event_hash != expected_previous:
            raise PlaySessionError("play event hash chain is broken")
        result = _apply_logic_grid_play_action(
            session,
            puzzle,
            event_id=source.event_id,
            action=source.action,
            verify_session=False,
        )
        if result.session.events[-1] != source:
            raise PlaySessionError("play event does not match its deterministic replay")
        session = result.session
    return session
