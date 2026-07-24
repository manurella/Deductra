# Logic Grid Attempt Persistence

FAM-LG-009 provides the local durability boundary for Logic Grid play. It stores the complete
FAM-LG-008 event history, rebuilds the current session from the immutable puzzle on every trusted
read, and derives descriptive attempt evidence without converting tentative marks into proof.
FAM-LG-011 extends the same adapter with a second, independent log that durably retains
already cross-verified move evaluations and normalizes their decided outcomes into common memory.

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

The common memory bridge therefore normalizes only three authoritative facts:

- `AttemptStarted` when the durable attempt is created;
- `AttemptCompleted` only after the play session's independent final checker accepted completion; and
- `MoveEvaluated` for each decided move evaluation recorded through FAM-LG-011, described below.

Tentative assignments, exclusions, structural validation outcomes, undo, redo, pause, checkpoints,
and rejected interface actions still do not become `MoveEvaluated` events on their own. Only an
already cross-verified evaluation, submitted through the dedicated assistance-recording operation,
can normalize into one.

## Move evaluation evidence

FAM-LG-011 adds a second append-only log, parallel to the play-event log, that retains complete
`LogicGridMoveEvaluation` documents produced by the separate FAM-LG-010 assistance service.
`record_move_evaluation` is independent of `append`: it never mutates the play event stream, and it
accepts only an evaluation whose attempt identity, puzzle revision, source event, and source session
hash all match the attempt's current durable head. A stale or foreign evaluation is rejected before
it reaches storage.

Each `ObservedMoveEvaluation` pairs one sealed evaluation with a local observation time and a hash
of its predecessor, forming its own tamper-evident chain. Because cross-verification already ran
once when the evaluation was produced, reads do not repeat it; they instead recompute and compare
every stored hash, exactly as the play log already does for its own events, without invoking either
solver backend again.

Only `supported` and `contradicted` evaluations normalize into `MoveEvaluated`, each identified by
the evaluation's own content hash so a repeated identical evaluation adds durable evidence without
being double-counted in the common projection. `inconclusive` and `quarantined` evaluations remain
in the durable log for audit but never become a projection fact. An evaluation observed at or after
the session's completion time is retained but excluded from the projection stream, preserving the
rule that no attempt stream carries an event after its terminal fact. The verified technique's rule
identity, when present, becomes the projection's `rule_id`; the shared `MoveEvaluated.duration_ms`
field, which this integration does not measure, is fixed at zero rather than approximated. See
[ADR-0021](decisions/0021-persist-verified-move-evaluations-into-attempt-memory.md).

## Public contract

`PersistedLogicGridAttempt` is immutable and versioned as `1.1.0`. It contains the user identity,
start and update times, observed play events, observed move evaluations, replayed session,
descriptive action evidence, normalized lifecycle events, rebuilt common attempt projection, and a
complete record hash. The checked-in major-version schema is
`schemas/logic-grid-attempt-record-v1.schema.json`.

The persistence API accepts typed in-memory values and an explicit database path. It performs no
implicit home-directory discovery, environment lookup, cloud synchronization, or network access.
Callers retain responsibility for choosing and protecting the local database location.

## Deliberate exclusions

FAM-LG-011 stores no hint evidence and adds no timers, abandonment or deletion workflow,
retention policy, learning inference, mastery score, puzzle library, synchronization, encryption
key management, telemetry, terminal interface, generation, or report composition. Exact privacy
deletion and backup behavior remain a later owner-reviewed security decision. The adapter exposes
no raw SQL or mutable projection operation through its public port, and it never re-verifies a
stored evaluation against the solver backends.
