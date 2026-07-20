# Logic Grid Attempt Persistence

FAM-LG-009 provides the local durability boundary for Logic Grid play. It stores the complete
FAM-LG-008 event history, rebuilds the current session from the immutable puzzle on every trusted
read, and derives descriptive attempt evidence without converting tentative marks into proof.

## Durable source of truth

The canonical source remains the ordered `PlayEvent` stream. A stored attempt begins with an empty
session, a caller-supplied local user identifier, a timezone-aware start time, one puzzle revision,
and one validation mode. Each later append must add exactly one event to the verified durable head.
The adapter rejects stale branches, duplicate attempt or event identifiers, changed puzzle
revisions, backwards observation times, gaps, altered hashes, and supplied sessions that differ
from deterministic replay.

`ObservedPlayEvent` pairs each canonical event with the time at which the local application
persisted it. Its own digest covers both values. Observation time is evidence about storage order;
it is not a gameplay timer, elapsed-time claim, or performance score.

## Transaction and recovery model

`LogicGridAttemptStore` is the application-facing port. `SQLiteLogicGridAttemptStore` is the first
adapter and uses the Python standard library. File-backed databases enable foreign keys,
write-ahead logging, and a bounded busy timeout. Creation and append use `BEGIN IMMEDIATE` so the
event row, indexed stream head, complete record hash, and disposable projections change in one
transaction.

SQLite stores canonical JSON alongside indexed identity, sequence, lifecycle, and hash values.
Reads parse both representations, compare every index with its typed value, replay all play events,
rebuild every projection, and require equality with the stored record. A failed append rolls back
without advancing the stream. Concurrent callers must reload after a stale-head conflict; the
adapter never selects or merges a branch implicitly.

The schema uses dedicated `logic_grid_attempt_*` tables and a dedicated migration ledger. It can
share a database file with other Deductra SQLite adapters without sharing table authority. Breaking
storage changes require an additive migration plan and a new architecture decision.

## Descriptive attempt evidence

`LogicGridAttemptEvidence` counts accepted and rejected application outcomes by exact play-action
kind and cites every source event identifier. It records the attempt status and the source event,
session, and projection hashes. This view answers what interaction occurred; it does not say that a
mark was logically correct, independently derived, or evidence of mastery.

The common memory bridge therefore normalizes only two authoritative lifecycle facts:

- `AttemptStarted` when the durable attempt is created; and
- `AttemptCompleted` only after the play session's independent final checker accepted completion.

Tentative assignments, exclusions, structural validation outcomes, undo, redo, pause, checkpoints,
and rejected interface actions do not become `MoveEvaluated` events. A future learning packet may
record evaluated moves only when it can cite an established reasoning or verification authority.
Until then, the common attempt projection deliberately reports zero evaluated moves.

## Public contract

`PersistedLogicGridAttempt` is immutable and versioned as `1.0.0`. It contains the user identity,
start and update times, observed play events, replayed session, descriptive action evidence,
normalized lifecycle events, rebuilt common attempt projection, and a complete record hash. The
checked-in major-version schema is
`schemas/logic-grid-attempt-record-v1.schema.json`.

The persistence API accepts typed in-memory values and an explicit database path. It performs no
implicit home-directory discovery, environment lookup, cloud synchronization, or network access.
Callers retain responsibility for choosing and protecting the local database location.

## Deliberate exclusions

FAM-LG-009 adds no clue-level evaluation, hint evidence, timers, abandonment or deletion workflow,
retention policy, learning inference, mastery score, puzzle library, synchronization, encryption
key management, telemetry, terminal interface, generation, or report composition. Exact privacy
deletion and backup behavior remain a later owner-reviewed security decision. The adapter exposes
no raw SQL or mutable projection operation through its public port.
