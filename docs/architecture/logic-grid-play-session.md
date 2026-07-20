# Logic Grid Play Session

FAM-LG-007 establishes the presentation-neutral interaction contract for one Logic Grid attempt.
It turns fixed puzzle givens and tentative user marks into an immutable current view backed by a
complete, tamper-evident action history. Terminal and graphical adapters can consume this boundary
without placing domain state inside widgets.

## Interaction model

A session starts from one immutable puzzle revision and one caller-supplied attempt identifier.
Fixed assignments and exclusions are projected from the puzzle; user actions cannot change them.
The v1 action vocabulary supports assigning, excluding, or clearing a cell; undoing an active
move; redoing a selected retained child; and requesting a completion check.

Assignments and exclusions are tentative play marks. Their presence does not claim that a human
rule or proof backend verified a deduction. Only the established reasoning and verification
boundaries may issue verified reasoning state.

Every action receives a stable outcome code and corrective, presentation-safe message. Unknown
puzzle references, fixed-cell edits, unavailable redo targets, completion failures, and actions
after completion fail without changing the active marks. Rejected outcomes remain in history so
replay does not conceal what happened.

## Non-destructive history

Accepted cell actions form a retained move graph. Each move references the move that was active
when it was applied. Undo changes the active history cursor to the parent; redo names one direct
child. Applying a different move after undo creates a new retained branch. No action deletes or
rewrites an earlier event.

The complete event sequence is contiguous and SHA-256 chained. Each event records the resulting
move cursor and state hash. A session also carries separate hashes for its active marks and its
complete history. Replay recomputes every outcome from the original puzzle and rejects broken
chains, altered outcomes, impossible cursor movement, and sessions that differ from replay.

## Completion authority

A completion request passes the active assignment set to the independent Logic Grid final checker.
The session becomes completed only when that checker confirms completeness, fixed givens,
category bijections, and every normalized clue. Incomplete or incorrect attempts remain active.
Completed sessions retain later rejected actions but cannot change state.

## Public contract

`LogicGridPlaySession` is immutable and versioned as `1.0.0`. Its checked-in schema is
`schemas/logic-grid-play-session-v1.schema.json`. The public service accepts in-memory typed values;
identifiers are bounded by the common domain contract, and no raw parser exceptions or supplied
source documents are retained.
The contract caps each in-memory attempt at 10,000 events so replay work and retained history remain
bounded before persistence policy exists.

## Deliberate exclusions

This packet does not provide validation modes, automated mistake disclosure, hints, timers, pause,
named checkpoints, persistence, learning projections, puzzle selection, filesystem behavior,
terminal widgets, solve orchestration, generation, reports, or telemetry. Those capabilities must
consume the play-session contract in later bounded packets and must not reinterpret tentative marks
as proof.
