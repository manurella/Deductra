"""Immutable, replayable Logic Grid play-session application service."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.base import DomainModel
from deductra.domain.ids import (
    AttemptId,
    EventId,
    Identifier,
    PuzzleRevisionId,
    ValueId,
    VariableId,
)
from deductra.domain.serialization import canonical_sha256
from deductra.families.logic_grid.checker import check_logic_grid_solution
from deductra.families.logic_grid.specification import LogicGridSpec

PLAY_SCHEMA_VERSION = "1.1.0"
PLAY_GENESIS_HASH = "0" * 64
MAX_PLAY_EVENTS = 10_000
type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type CheckpointName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]


class PlayValidationMode(StrEnum):
    """When structural progress conflicts are disclosed to the player."""

    STRICT = "strict"
    SOFT = "soft"
    DEFERRED = "deferred"
    EXAM = "exam"


class PlaySessionStatus(StrEnum):
    """Terminal status of a presentation-neutral play attempt."""

    ACTIVE = "active"
    PAUSED = "paused"
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


class ValidateProgress(DomainModel):
    """Request structural progress validation when the mode permits it."""

    kind: Literal["validate_progress"] = "validate_progress"


class PauseSession(DomainModel):
    """Pause interaction without changing the current history position."""

    kind: Literal["pause_session"] = "pause_session"


class ResumeSession(DomainModel):
    """Resume a paused interaction session."""

    kind: Literal["resume_session"] = "resume_session"


class CreateCheckpoint(DomainModel):
    """Name the current retained history position."""

    kind: Literal["create_checkpoint"] = "create_checkpoint"
    name: CheckpointName


class RestoreCheckpoint(DomainModel):
    """Move the active cursor to a retained named checkpoint."""

    kind: Literal["restore_checkpoint"] = "restore_checkpoint"
    checkpoint_id: EventId


type PlayAction = Annotated[
    AssignCell
    | ExcludeCell
    | ClearCell
    | UndoMove
    | RedoMove
    | CheckCompletion
    | ValidateProgress
    | PauseSession
    | ResumeSession
    | CreateCheckpoint
    | RestoreCheckpoint,
    Field(discriminator="kind"),
]
type CellAction = AssignCell | ExcludeCell | ClearCell


class PlayConflict(DomainModel):
    """Presentation-safe structural conflict in tentative play marks."""

    code: Literal["duplicate_row", "no_candidate"]
    references: tuple[Identifier, ...]
    message: str

    @model_validator(mode="after")
    def validate_conflict(self) -> PlayConflict:
        if not self.references or not self.message:
            raise ValueError("play conflicts require references and a message")
        if self.references != tuple(sorted(set(self.references))):
            raise ValueError("play conflict references must be unique and sorted")
        return self


class PlayCheckpoint(DomainModel):
    """A named reference to one retained move cursor and captured state."""

    checkpoint_id: EventId
    name: CheckpointName
    move_id: EventId | None = None
    captured_sequence_no: Annotated[int, Field(ge=0)]
    captured_state_hash: Sha256Digest


class PlayEvent(DomainModel):
    """One retained interaction outcome in a tamper-evident attempt stream."""

    event_id: EventId
    sequence_no: Annotated[int, Field(ge=0)]
    schema_version: Literal["1.1.0"] = PLAY_SCHEMA_VERSION
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

    schema_version: Literal["1.1.0"] = PLAY_SCHEMA_VERSION
    attempt_id: AttemptId
    puzzle_revision_id: PuzzleRevisionId
    validation_mode: PlayValidationMode = PlayValidationMode.SOFT
    status: PlaySessionStatus
    assignments: tuple[AssignmentAtom, ...]
    exclusions: tuple[ExclusionAtom, ...]
    conflicts: tuple[PlayConflict, ...] = ()
    checkpoints: tuple[PlayCheckpoint, ...] = ()
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
        conflict_keys = tuple((item.code, item.references) for item in self.conflicts)
        if conflict_keys != tuple(sorted(conflict_keys)):
            raise ValueError("play conflicts must use canonical order")
        checkpoint_ids = tuple(item.checkpoint_id for item in self.checkpoints)
        if len(checkpoint_ids) != len(set(checkpoint_ids)):
            raise ValueError("checkpoint identifiers must be unique")
        checkpoint_names = tuple(item.name.casefold() for item in self.checkpoints)
        if len(checkpoint_names) != len(set(checkpoint_names)):
            raise ValueError("checkpoint names must be unique ignoring case")
        if tuple(item.captured_sequence_no for item in self.checkpoints) != tuple(
            sorted(item.captured_sequence_no for item in self.checkpoints)
        ):
            raise ValueError("checkpoints must use capture order")
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
            "validation_mode": session.validation_mode,
            "status": session.status,
            "assignments": session.assignments,
            "exclusions": session.exclusions,
            "conflicts": session.conflicts,
            "checkpoints": session.checkpoints,
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
    validation_mode: PlayValidationMode,
    status: PlaySessionStatus,
    assignments: dict[VariableId, ValueId],
    exclusions: set[tuple[VariableId, ValueId]],
    conflicts: tuple[PlayConflict, ...],
    checkpoints: tuple[PlayCheckpoint, ...],
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
        validation_mode=validation_mode,
        status=status,
        assignments=ordered_assignments,
        exclusions=ordered_exclusions,
        conflicts=conflicts,
        checkpoints=checkpoints,
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
    validation_mode: PlayValidationMode = PlayValidationMode.SOFT,
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
        validation_mode=validation_mode,
        status=PlaySessionStatus.ACTIVE,
        assignments=assignments,
        exclusions=exclusions,
        conflicts=(),
        checkpoints=(),
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


def _progress_conflicts(
    puzzle: LogicGridSpec,
    assignments: dict[VariableId, ValueId],
    exclusions: set[tuple[VariableId, ValueId]],
) -> tuple[PlayConflict, ...]:
    """Return deterministic structural conflicts without evaluating clue correctness."""
    anchor_category = next(
        item for item in puzzle.categories if item.category_id == puzzle.anchor_category_id
    )
    anchor_domain = next(
        item for item in puzzle.domains if item.domain_id == anchor_category.domain_id
    )
    anchor_values = {item.value_id for item in anchor_domain.values}
    conflicts: list[PlayConflict] = []

    for variable in puzzle.variables:
        if variable.variable_id in assignments:
            continue
        remaining = anchor_values - {
            value_id for variable_id, value_id in exclusions if variable_id == variable.variable_id
        }
        if not remaining:
            conflicts.append(
                PlayConflict(
                    code="no_candidate",
                    references=(variable.variable_id,),
                    message="A puzzle item has no remaining row candidate.",
                )
            )

    for category in puzzle.categories:
        variables_by_value: dict[ValueId, list[VariableId]] = {}
        for variable_id in category.variable_ids:
            value_id = assignments.get(variable_id)
            if value_id is not None:
                variables_by_value.setdefault(value_id, []).append(variable_id)
        for value_id, variable_ids in variables_by_value.items():
            if len(variable_ids) > 1:
                conflicts.append(
                    PlayConflict(
                        code="duplicate_row",
                        references=tuple(sorted({category.category_id, value_id, *variable_ids})),
                        message="Two items in one category select the same row.",
                    )
                )

    return tuple(sorted(conflicts, key=lambda item: (item.code, item.references)))


def _automatic_conflicts(
    mode: PlayValidationMode,
    puzzle: LogicGridSpec,
    assignments: dict[VariableId, ValueId],
    exclusions: set[tuple[VariableId, ValueId]],
) -> tuple[PlayConflict, ...]:
    if mode in {PlayValidationMode.STRICT, PlayValidationMode.SOFT}:
        return _progress_conflicts(puzzle, assignments, exclusions)
    return ()


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
    conflicts: tuple[PlayConflict, ...] | None = None,
    checkpoints: tuple[PlayCheckpoint, ...] | None = None,
) -> PlayActionResult:
    resulting_conflicts = session.conflicts if conflicts is None else conflicts
    resulting_checkpoints = session.checkpoints if checkpoints is None else checkpoints
    provisional = _build_session(
        attempt_id=session.attempt_id,
        puzzle_revision_id=session.puzzle_revision_id,
        validation_mode=session.validation_mode,
        status=status,
        assignments=assignments,
        exclusions=exclusions,
        conflicts=resulting_conflicts,
        checkpoints=resulting_checkpoints,
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
        validation_mode=session.validation_mode,
        status=status,
        assignments=assignments,
        exclusions=exclusions,
        conflicts=resulting_conflicts,
        checkpoints=resulting_checkpoints,
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
            validation_mode=session.validation_mode,
            events=session.events,
        )
        if replayed != session:
            raise PlaySessionError("session does not equal its canonical replay")

    assignments = {item.variable_id: item.value_id for item in session.assignments}
    exclusions = {(item.variable_id, item.value_id) for item in session.exclusions}
    head = session.active_move_id
    moves = _move_events(session.events)
    if session.status is PlaySessionStatus.COMPLETED:
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

    if isinstance(action, ResumeSession):
        accepted = session.status is PlaySessionStatus.PAUSED
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=accepted,
            code="session_resumed" if accepted else "session_not_paused",
            message=(
                "The play session resumed." if accepted else "The play session is already active."
            ),
            parent_move_id=head,
            resulting_move_id=head,
            status=PlaySessionStatus.ACTIVE if accepted else session.status,
            assignments=assignments,
            exclusions=exclusions,
        )

    if isinstance(action, PauseSession):
        accepted = session.status is PlaySessionStatus.ACTIVE
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=accepted,
            code="session_paused" if accepted else "session_already_paused",
            message=(
                "The play session paused." if accepted else "The play session is already paused."
            ),
            parent_move_id=head,
            resulting_move_id=head,
            status=PlaySessionStatus.PAUSED,
            assignments=assignments,
            exclusions=exclusions,
        )

    if isinstance(action, CreateCheckpoint):
        duplicate = action.name.casefold() in {item.name.casefold() for item in session.checkpoints}
        if duplicate:
            return _append_outcome(
                session,
                event_id=event_id,
                action=action,
                accepted=False,
                code="checkpoint_name_exists",
                message="Choose a checkpoint name that is not already in use.",
                parent_move_id=head,
                resulting_move_id=head,
                status=session.status,
                assignments=assignments,
                exclusions=exclusions,
            )
        checkpoint = PlayCheckpoint(
            checkpoint_id=event_id,
            name=action.name,
            move_id=head,
            captured_sequence_no=len(session.events),
            captured_state_hash=session.state_hash,
        )
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=True,
            code="checkpoint_created",
            message="The current history position was saved as a checkpoint.",
            parent_move_id=head,
            resulting_move_id=head,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
            checkpoints=(*session.checkpoints, checkpoint),
        )

    if session.status is PlaySessionStatus.PAUSED:
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=False,
            code="session_paused",
            message="Resume the play session before changing or checking the puzzle.",
            parent_move_id=head,
            resulting_move_id=head,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
        )

    if isinstance(action, RestoreCheckpoint):
        checkpoint = next(
            (item for item in session.checkpoints if item.checkpoint_id == action.checkpoint_id),
            None,
        )
        if checkpoint is None:
            return _append_outcome(
                session,
                event_id=event_id,
                action=action,
                accepted=False,
                code="checkpoint_unavailable",
                message="Choose a retained checkpoint from this play session.",
                parent_move_id=head,
                resulting_move_id=head,
                status=session.status,
                assignments=assignments,
                exclusions=exclusions,
            )
        target = checkpoint.move_id
        assignments, exclusions = _project_marks(puzzle, moves, target)
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=True,
            code="checkpoint_restored",
            message="The retained checkpoint was restored without deleting later history.",
            parent_move_id=head,
            resulting_move_id=target,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
            conflicts=_automatic_conflicts(
                session.validation_mode,
                puzzle,
                assignments,
                exclusions,
            ),
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
        next_assignments = assignments.copy()
        next_exclusions = set(exclusions)
        _apply_cell_action(next_assignments, next_exclusions, action)
        next_conflicts = _progress_conflicts(puzzle, next_assignments, next_exclusions)
        if session.validation_mode is PlayValidationMode.STRICT and next_conflicts:
            return _append_outcome(
                session,
                event_id=event_id,
                action=action,
                accepted=False,
                code="structural_conflict",
                message="That mark would create a structural puzzle conflict.",
                parent_move_id=head,
                resulting_move_id=head,
                status=session.status,
                assignments=assignments,
                exclusions=exclusions,
            )
        assignments = next_assignments
        exclusions = next_exclusions
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
            conflicts=(
                next_conflicts if session.validation_mode is PlayValidationMode.SOFT else ()
            ),
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
            conflicts=_automatic_conflicts(
                session.validation_mode,
                puzzle,
                assignments,
                exclusions,
            ),
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
            conflicts=_automatic_conflicts(
                session.validation_mode,
                puzzle,
                assignments,
                exclusions,
            ),
        )

    if isinstance(action, ValidateProgress):
        if session.validation_mode is PlayValidationMode.EXAM:
            return _append_outcome(
                session,
                event_id=event_id,
                action=action,
                accepted=False,
                code="validation_unavailable",
                message="Progress validation is unavailable in exam mode.",
                parent_move_id=head,
                resulting_move_id=head,
                status=session.status,
                assignments=assignments,
                exclusions=exclusions,
            )
        conflicts = _progress_conflicts(puzzle, assignments, exclusions)
        return _append_outcome(
            session,
            event_id=event_id,
            action=action,
            accepted=True,
            code="conflicts_found" if conflicts else "progress_structurally_valid",
            message=(
                "Structural conflicts were found in the current marks."
                if conflicts
                else "No structural conflicts were found; clue correctness remains unchecked."
            ),
            parent_move_id=head,
            resulting_move_id=head,
            status=session.status,
            assignments=assignments,
            exclusions=exclusions,
            conflicts=conflicts,
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
        conflicts=(
            _progress_conflicts(puzzle, assignments, exclusions)
            if not accepted and session.validation_mode is not PlayValidationMode.EXAM
            else ()
        ),
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
    validation_mode: PlayValidationMode = PlayValidationMode.SOFT,
    events: tuple[PlayEvent, ...],
) -> LogicGridPlaySession:
    """Rebuild an attempt and reject any non-canonical or tampered event stream."""
    session = start_logic_grid_play(
        puzzle,
        attempt_id=attempt_id,
        validation_mode=validation_mode,
    )
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
