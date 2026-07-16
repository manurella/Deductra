# ADR-0009: Derive memory views from immutable events

## Status

Accepted

## Date

2026-07-16

## Owner

Repository owner

## Context

Attempts, learning evidence, novelty lookup, and artifact discovery need query-oriented shapes that differ from their source histories. Treating these indexes as authoritative would create competing truths and make recovery, migration, and audit unreliable.

CR-008 requires exact rebuild behavior before persistence, recommendation, reporting, or product interfaces are added.

## Decision

Represent memory read models as immutable, canonically hashed projections derived through pure replay from typed, tamper-evident projection-source event streams.

Use separate stream kinds for attempts, novelty entries, and artifact metadata. Allow multiple attempt streams, one canonical novelty stream, and one canonical artifact stream in a rebuild. Reject ambiguous or invalid histories rather than selecting a winner.

The learning view remains descriptive: it aggregates event-backed counts by user and rule but makes no mastery, confidence, diagnostic, or recommendation claim.

Pair source events and the complete projection bundle in the versioned serialized contract. Validation repeats a clean rebuild and rejects drift.

## Alternatives considered

- Update projection tables directly from product commands. Rejected because direct writes cannot prove rebuild equivalence.
- Store only snapshots or checkpoints. Rejected because accelerators cannot replace canonical event history.
- Calculate mastery and recommendations in the projection reducer. Rejected because inference policy is not part of CR-008 and would turn an observable read model into an unsupported authority.
- Add a new database schema and migration now. Rejected because the packet requires deterministic projection behavior, while durable stream ingestion and checkpoint operations need separate review.

## Consequences

All CR-008 views can be discarded and recreated from their events. Corruption and ambiguous stream topology fail closed. Novelty and artifact indexes remain metadata-only, minimizing accidental authority and artifact duplication.

Consumers must tolerate rebuildable, potentially stale views. A future persistence packet must store source events durably, perform atomic projection replacement, and treat checkpoints only as accelerators.

## Risks

Multiple event-envelope families now exist for distinct bounded contexts. Future ingestion must preserve their identities and hashes without translating away evidence. Large histories may eventually require checkpoints or incremental rebuilds, but those optimizations must reproduce a full replay exactly.

## Reconsideration triggers

Revisit this decision if full replay exceeds an approved recovery objective, if a source system cannot produce stable typed events, or if a projection schema migration cannot coexist with historical event versions.
