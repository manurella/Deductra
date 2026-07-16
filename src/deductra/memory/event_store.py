"""Technology-neutral repository contract for append-only reasoning events."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from deductra.domain.ids import TraceId
from deductra.reasoning.events import EventEnvelope
from deductra.reasoning.integrity import ChainVerification


class EventStoreError(RuntimeError):
    """Base error raised by canonical event-store implementations."""


class DuplicateEventError(EventStoreError):
    """An event identifier or stream sequence already exists."""


class StreamConflictError(EventStoreError):
    """An append does not continue the current stream head exactly."""


class StreamIntegrityError(EventStoreError):
    """An event or existing stream fails canonical integrity verification."""


@runtime_checkable
class EventStore(Protocol):
    """Append-only persistence port used by reasoning and replay services."""

    def append(self, event: EventEnvelope) -> None:
        """Atomically append one verified event to its trace stream."""
        ...

    def read_stream(
        self, trace_id: TraceId, *, after_sequence: int = -1
    ) -> tuple[EventEnvelope, ...]:
        """Read verified stored envelopes in ascending sequence order."""
        ...

    def latest(self, trace_id: TraceId) -> EventEnvelope | None:
        """Return the current stream head, if the stream exists."""
        ...

    def verify_stream(self, trace_id: TraceId) -> ChainVerification:
        """Verify the complete persisted event stream."""
        ...

    def close(self) -> None:
        """Release resources owned by the store."""
        ...
