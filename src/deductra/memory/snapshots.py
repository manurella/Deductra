"""Integrity-protected state snapshots used only as replay accelerators."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from deductra.domain.base import DomainModel
from deductra.domain.ids import BranchId, EventId, PuzzleRevisionId, SnapshotId
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.events import Sha256Digest
from deductra.reasoning.state import PuzzleState


class StateSnapshot(DomainModel):
    """A verifiable copy of one state and its authoritative source event."""

    snapshot_id: SnapshotId
    puzzle_revision_id: PuzzleRevisionId
    branch_id: BranchId
    sequence_no: Annotated[int, Field(ge=0)]
    source_event_id: EventId
    source_event_hash: Sha256Digest
    state: PuzzleState
    snapshot_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_snapshot(self) -> StateSnapshot:
        if (
            self.puzzle_revision_id != self.state.puzzle_revision_id
            or self.branch_id != self.state.branch_id
            or self.sequence_no != self.state.sequence_no
        ):
            raise ValueError("snapshot identity must match its state")
        if self.snapshot_hash != compute_snapshot_hash(self):
            raise ValueError("snapshot_hash does not match the canonical snapshot")
        return self


def compute_snapshot_hash(snapshot: StateSnapshot) -> str:
    """Hash every canonical snapshot field except the digest itself."""
    return canonical_sha256(snapshot.model_dump(mode="json", exclude={"snapshot_hash"}))


def create_snapshot(
    *,
    snapshot_id: SnapshotId,
    state: PuzzleState,
    source_event_id: EventId,
    source_event_hash: str,
) -> StateSnapshot:
    """Seal one immutable state snapshot against accidental or malicious drift."""
    unsigned = StateSnapshot.model_construct(
        snapshot_id=snapshot_id,
        puzzle_revision_id=state.puzzle_revision_id,
        branch_id=state.branch_id,
        sequence_no=state.sequence_no,
        source_event_id=source_event_id,
        source_event_hash=source_event_hash,
        state=state,
        snapshot_hash="0" * 64,
    )
    return StateSnapshot(
        snapshot_id=snapshot_id,
        puzzle_revision_id=state.puzzle_revision_id,
        branch_id=state.branch_id,
        sequence_no=state.sequence_no,
        source_event_id=source_event_id,
        source_event_hash=source_event_hash,
        state=state,
        snapshot_hash=compute_snapshot_hash(unsigned),
    )


def verify_snapshot(snapshot: StateSnapshot) -> bool:
    """Return whether a snapshot remains canonically intact."""
    return snapshot.snapshot_hash == compute_snapshot_hash(snapshot)
