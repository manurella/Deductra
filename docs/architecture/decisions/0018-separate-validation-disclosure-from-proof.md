# ADR-0018: Separate validation disclosure from proof

## Status

Accepted

## Context

Play needs strict, soft, deferred, and exam experiences, but tentative grid marks are not verified
deductions. Treating a conflict-free partial grid as correct would leak solver authority into the
interaction layer. Pause and checkpoints also need predictable recovery without creating a second
mutable state source or deleting later actions.

## Decision

Fix one validation-disclosure mode when a play attempt starts. Detect only family-structural
conflicts that follow directly from candidate availability and category bijections. Strict mode
rejects such conflicts, soft mode exposes them immediately, deferred mode exposes them only on
request or failed completion, and exam mode withholds progress validation. Never claim that the
absence of a structural conflict proves clue correctness.

Represent pause, resume, checkpoint creation, and checkpoint restoration as ordinary retained play
events. A checkpoint names an existing move cursor and captures its sequence and state hash.
Restoration reprojects from retained moves and does not remove later history. Continue to authorize
completion only through the independent final checker.

Evolve the pre-release play-session major-v1 contract additively from `1.0.0` to `1.1.0`. No
persistence adapter or released play-session artifact existed at `1.0.0`; later persisted revisions
must define an explicit compatibility and migration policy.

## Consequences

- Presentation layers receive predictable validation disclosure without gaining proof authority.
- Strict mode prevents deterministic grid-structure conflicts but does not promise that each
  accepted move satisfies every clue.
- Pause and checkpoints are exactly replayable and cannot erase exploration history.
- Checkpoint names and attempt history are bounded at the typed boundary.
- Clue-level mistake evaluation, hints, persistence, timing, and terminal behavior remain later
  work.
