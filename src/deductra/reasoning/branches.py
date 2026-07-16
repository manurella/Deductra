"""Explicit retained branch projections for contradiction-safe replay."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from deductra.domain.atoms import Atom
from deductra.domain.base import DomainModel
from deductra.domain.ids import BranchId
from deductra.reasoning.events import (
    BranchClosed,
    BranchOpened,
    CandidatesEliminated,
    ContradictionDetected,
    EventEnvelope,
    Sha256Digest,
    ValueAssigned,
)
from deductra.reasoning.integrity import verify_event
from deductra.reasoning.state import PuzzleState


class BranchRecord(DomainModel):
    """Lifecycle and provenance for one retained reasoning branch."""

    branch_id: BranchId
    parent_branch_id: BranchId | None = None
    opened_from_state_hash: Sha256Digest
    assumption: Atom | None = None
    method: Literal["root", "assumption", "search", "demonstration"]
    status: Literal["open", "contradicted", "solved", "abandoned"] = "open"
    opened_sequence_no: Annotated[int, Field(ge=0)]
    closed_sequence_no: Annotated[int, Field(ge=0)] | None = None
    latest_state_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_branch_identity(self) -> BranchRecord:
        if self.method == "root":
            if self.parent_branch_id is not None or self.assumption is not None:
                raise ValueError("root branches cannot have a parent or assumption")
        elif self.parent_branch_id is None or self.assumption is None:
            raise ValueError("non-root branches require a parent and assumption")
        if self.status == "open" and self.closed_sequence_no is not None:
            raise ValueError("open branches cannot have a close sequence")
        if self.status in {"solved", "abandoned"} and self.closed_sequence_no is None:
            raise ValueError("solved and abandoned branches require a close sequence")
        return self


class BranchProjection(DomainModel):
    """Immutable latest state per branch plus the currently active branch."""

    sequence_no: Annotated[int, Field(ge=0)]
    active_branch_id: BranchId
    branches: tuple[BranchRecord, ...]
    states: tuple[PuzzleState, ...]

    @model_validator(mode="after")
    def validate_projection(self) -> BranchProjection:
        branch_ids = tuple(record.branch_id for record in self.branches)
        state_ids = tuple(state.branch_id for state in self.states)
        if len(branch_ids) != len(set(branch_ids)) or len(state_ids) != len(set(state_ids)):
            raise ValueError("branch projections must contain unique branch identifiers")
        if set(branch_ids) != set(state_ids):
            raise ValueError("every branch record must have exactly one retained state")
        if self.active_branch_id not in set(branch_ids):
            raise ValueError("active branch must exist in the retained projection")
        if any(
            record.parent_branch_id is not None and record.parent_branch_id not in set(branch_ids)
            for record in self.branches
        ):
            raise ValueError("branch parents must remain in the retained projection")
        state_by_branch = {state.branch_id: state for state in self.states}
        if any(
            record.latest_state_hash != state_by_branch[record.branch_id].state_hash
            for record in self.branches
        ):
            raise ValueError("branch records must reference their retained state hashes")
        return self

    def state_for(self, branch_id: BranchId) -> PuzzleState:
        """Return one retained branch state."""
        return next(state for state in self.states if state.branch_id == branch_id)

    def record_for(self, branch_id: BranchId) -> BranchRecord:
        """Return one retained branch record."""
        return next(record for record in self.branches if record.branch_id == branch_id)

    @property
    def active_state(self) -> PuzzleState:
        """Return the state currently selected for further reduction."""
        return self.state_for(self.active_branch_id)


def create_branch_projection(genesis: PuzzleState) -> BranchProjection:
    """Create the root retained-branch projection from a verified genesis state."""
    root = BranchRecord(
        branch_id=genesis.branch_id,
        opened_from_state_hash=genesis.state_hash,
        method="root",
        opened_sequence_no=genesis.sequence_no,
        latest_state_hash=genesis.state_hash,
    )
    return BranchProjection(
        sequence_no=genesis.sequence_no,
        active_branch_id=genesis.branch_id,
        branches=(root,),
        states=(genesis,),
    )


def _replace_state(
    projection: BranchProjection,
    state: PuzzleState,
    *,
    status: Literal["open", "contradicted", "solved", "abandoned"] | None = None,
) -> tuple[tuple[BranchRecord, ...], tuple[PuzzleState, ...]]:
    records = tuple(
        record.model_copy(
            update={
                "latest_state_hash": state.state_hash,
                "status": status or record.status,
            }
        )
        if record.branch_id == state.branch_id
        else record
        for record in projection.branches
    )
    states = tuple(
        state if current.branch_id == state.branch_id else current for current in projection.states
    )
    return records, states


def _validate_origin(record: BranchRecord, payload: CandidatesEliminated | ValueAssigned) -> None:
    if record.method == "search" and payload.origin != "search":
        from deductra.reasoning.reducer import SearchDisclosureError

        raise SearchDisclosureError("search-branch mutations must be disclosed as search")
    if record.method != "search" and payload.origin == "search":
        from deductra.reasoning.reducer import SearchDisclosureError

        raise SearchDisclosureError("search mutations require an explicit search branch")


def reduce_branch_projection(
    projection: BranchProjection,
    event: EventEnvelope,
) -> BranchProjection:
    """Apply one ordered event while preserving every historical branch state."""
    from deductra.reasoning.reducer import StateConflictError, derive_branch_state, reduce_state

    if not verify_event(event):
        raise StateConflictError("event integrity verification failed")
    if event.sequence_no <= projection.sequence_no:
        raise StateConflictError("event sequence must advance the projection")
    if event.puzzle_revision_id != projection.active_state.puzzle_revision_id:
        raise StateConflictError("event puzzle revision does not match the projection")

    payload = event.payload
    known_branches = {record.branch_id for record in projection.branches}
    if not isinstance(payload, BranchOpened) and event.branch_id not in known_branches:
        raise StateConflictError("event references an unknown retained branch")
    if isinstance(payload, BranchOpened):
        if event.branch_id in known_branches:
            raise StateConflictError("branch identifier already exists")
        if payload.parent_branch_id != projection.active_branch_id:
            raise StateConflictError("new branches must open from the active branch")
        if projection.record_for(projection.active_branch_id).status != "open":
            raise StateConflictError("new branches require an open parent branch")
        parent = projection.active_state
        child = derive_branch_state(parent, event, payload)
        record = BranchRecord(
            branch_id=event.branch_id,
            parent_branch_id=parent.branch_id,
            opened_from_state_hash=parent.state_hash,
            assumption=payload.assumption,
            method=payload.method,
            opened_sequence_no=event.sequence_no,
            latest_state_hash=child.state_hash,
        )
        return BranchProjection(
            sequence_no=event.sequence_no,
            active_branch_id=event.branch_id,
            branches=(*projection.branches, record),
            states=(*projection.states, child),
        )

    if isinstance(payload, BranchClosed):
        if event.branch_id != projection.active_branch_id:
            raise StateConflictError("only the active branch can be closed")
        record = projection.record_for(event.branch_id)
        state = projection.state_for(event.branch_id)
        if record.parent_branch_id is None:
            raise StateConflictError("the root branch cannot be closed")
        if payload.source_state_hash != state.state_hash:
            raise StateConflictError("branch close source hash does not match retained state")
        if payload.status == "contradicted" and record.status != "contradicted":
            raise StateConflictError("contradicted closure requires a contradiction event")
        if payload.status == "solved" and not state.solved:
            raise StateConflictError("solved closure requires a solved branch state")
        records = tuple(
            current.model_copy(
                update={"status": payload.status, "closed_sequence_no": event.sequence_no}
            )
            if current.branch_id == record.branch_id
            else current
            for current in projection.branches
        )
        return BranchProjection(
            sequence_no=event.sequence_no,
            active_branch_id=record.parent_branch_id,
            branches=records,
            states=projection.states,
        )

    if isinstance(payload, (CandidatesEliminated, ValueAssigned, ContradictionDetected)):
        if event.branch_id != projection.active_branch_id:
            raise StateConflictError("state mutations must target the active branch")
        record = projection.record_for(event.branch_id)
        if record.status != "open":
            raise StateConflictError("closed or contradicted branches cannot accept mutations")
        if isinstance(payload, (CandidatesEliminated, ValueAssigned)):
            _validate_origin(record, payload)
        state = reduce_state(projection.state_for(event.branch_id), event)
        status = "contradicted" if isinstance(payload, ContradictionDetected) else None
        records, states = _replace_state(projection, state, status=status)
        return BranchProjection(
            sequence_no=event.sequence_no,
            active_branch_id=projection.active_branch_id,
            branches=records,
            states=states,
        )

    return projection.model_copy(update={"sequence_no": event.sequence_no})
