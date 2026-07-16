"""Persistence ports and adapters for canonical Deductra history."""

from deductra.memory.event_store import (
    DuplicateEventError,
    EventStore,
    EventStoreError,
    StreamConflictError,
    StreamIntegrityError,
)
from deductra.memory.snapshots import (
    StateSnapshot,
    compute_snapshot_hash,
    create_snapshot,
    verify_snapshot,
)
from deductra.memory.sqlite_store import SQLiteEventStore

__all__ = [
    "DuplicateEventError",
    "EventStore",
    "EventStoreError",
    "SQLiteEventStore",
    "StateSnapshot",
    "StreamConflictError",
    "StreamIntegrityError",
    "compute_snapshot_hash",
    "create_snapshot",
    "verify_snapshot",
]
