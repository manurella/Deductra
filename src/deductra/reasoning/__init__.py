"""Canonical reasoning-event contracts and integrity verification."""

from deductra.reasoning.events import (
    EventEnvelope,
    InitialStateCreated,
    ProducerRef,
    PuzzleValidated,
    TraceCompleted,
    TraceFailed,
    TraceStarted,
)
from deductra.reasoning.integrity import (
    GENESIS_EVENT_HASH,
    ChainVerification,
    compute_event_hash,
    seal_event,
    verify_chain,
    verify_event,
)

__all__ = [
    "GENESIS_EVENT_HASH",
    "ChainVerification",
    "EventEnvelope",
    "InitialStateCreated",
    "ProducerRef",
    "PuzzleValidated",
    "TraceCompleted",
    "TraceFailed",
    "TraceStarted",
    "compute_event_hash",
    "seal_event",
    "verify_chain",
    "verify_event",
]
