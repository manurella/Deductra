# ADR-0019: Persist play before projecting attempt evidence

## Status

Accepted

## Date

2026-07-20

## Owner

Repository owner

## Context

Logic Grid play now has deterministic, tamper-evident history, but process exit loses that history.
The product also needs local progress evidence. A play action can be accepted because it is a valid
state transition while still being an unverified tentative mark. Mapping that outcome directly to
an accepted learning move would overstate correctness and undermine the separation between
interaction, reasoning, and proof.

The existing common memory contract can rebuild attempt lifecycle and evaluated-move projections,
but it intentionally did not choose a durable ingestion adapter. The first family integration must
retain exact replay, avoid competing sources of truth, and make concurrent writes fail visibly.

## Decision

Persist the complete Logic Grid play-event stream through a family-specific port and transactional
SQLite adapter. Store immutable local observation times with the events, verify indexed and typed
representations on every read, and rebuild the session from the supplied immutable puzzle before
returning any record.

Treat the play log as canonical and all attempt summaries as disposable projections. Derive a
descriptive action-count view that cites all play event identifiers but makes no correctness or
mastery claim. Normalize only attempt start and independently verified completion into the common
memory event stream. Do not translate tentative play outcomes into `MoveEvaluated`.

Atomically append the event, advance the indexed stream head, and replace the derived record within
one immediate SQLite transaction. Reject stale writers rather than merging branches. Keep SQLite
imports confined to the named adapter and publish a strict versioned record schema.

## Alternatives considered

- Store only the latest serialized session. Rejected because an overwritten blob cannot prove an
  append-only history or isolate partial writes.
- Reuse the common reasoning `EventEnvelope` for play actions. Rejected because family interaction
  is not a reasoning trace and would expand the inner protocol with presentation workflow details.
- Map every accepted play action to an accepted evaluated move. Rejected because state-transition
  acceptance is not logical correctness and would produce misleading learning evidence.
- Persist only common memory events. Rejected because start and completion events cannot reconstruct
  marks, branches, checkpoints, rejected actions, or exact play replay.
- Introduce a family-neutral interaction persistence framework. Rejected until a second family
  demonstrates stable shared semantics.

## Consequences

An interrupted local play session can be reconstructed exactly and its descriptive evidence can be
discarded and rebuilt. Corrupted JSON, indexes, hashes, replay, or projections fail closed. Common
memory can observe active versus verified-completed attempts without treating tentative marks as
proof.

The adapter requires the matching immutable puzzle to read a stored attempt; a later puzzle library
must resolve that revision before resume. The stored record duplicates disposable projections for
fast inspection, but equality with clean replay is mandatory. Deletion, redaction, retention,
backup, and schema migration operations still require explicit product and security policy.

## Risks

Database growth is bounded per attempt by the existing 10,000-event play limit but not yet by a
repository-wide retention policy. A damaged or unavailable puzzle revision prevents trusted
resume. Multiple envelope families remain distinct, so future consolidation must preserve source
identity rather than translating away evidence.

## Reconsideration triggers

Revisit this decision when a second puzzle family needs local play persistence, measured recovery
time justifies checkpoints, privacy policy defines deletion or redaction, cloud synchronization is
approved, or an evaluated-move service can cite verified reasoning evidence for tentative actions.
