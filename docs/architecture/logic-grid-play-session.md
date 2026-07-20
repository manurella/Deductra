# Logic Grid Play Session

FAM-LG-007 established the presentation-neutral interaction contract for one Logic Grid attempt.
FAM-LG-008 completes its lifecycle policy with validation modes, pause/resume, and named restorable
checkpoints. Fixed puzzle givens and tentative user marks form an immutable current view backed by a
complete, tamper-evident action history. Terminal and graphical adapters can consume this boundary
without placing domain state inside widgets.

FAM-LG-009 persists this contract through the separate
[Logic Grid attempt persistence](logic-grid-attempt-persistence.md) adapter. The play service itself
remains independent of filesystem and database policy.

## Interaction model

A session starts from one immutable puzzle revision, one caller-supplied attempt identifier, and one
validation mode. Fixed assignments and exclusions are projected from the puzzle; user actions
cannot change them. The v1 action vocabulary supports assigning, excluding, or clearing a cell;
undoing an active move; redoing a selected retained child; validating structural progress; pausing
and resuming; creating and restoring named checkpoints; and requesting a completion check.

Assignments and exclusions are tentative play marks. Their presence does not claim that a human
rule or proof backend verified a deduction. Only the established reasoning and verification
boundaries may issue verified reasoning state.

Every action receives a stable outcome code and corrective, presentation-safe message. Unknown
puzzle references, fixed-cell edits, unavailable redo or checkpoint targets, completion failures,
and disallowed paused or completed actions fail without changing active marks. Rejected outcomes
remain in history so replay does not conceal what happened.

## Validation disclosure

Validation is fixed when an attempt starts and changes only when structural conflicts are shown:

- `strict` rejects a mark that would duplicate a row within one category or remove an item's final
  row candidate;
- `soft` accepts tentative marks and immediately exposes those structural conflicts;
- `deferred` accepts marks without immediate disclosure and computes conflicts only when requested
  or when completion fails; and
- `exam` withholds progress validation and exposes no conflict detail before completion.

These checks enforce visible grid structure only. A conflict-free partial state is not described as
correct, entailed, or verified. Clue correctness remains unknown until the independent final checker
accepts a complete assignment.

## Non-destructive history and recovery

Accepted cell actions form a retained move graph. Each move references the move that was active
when it was applied. Undo changes the active history cursor to the parent; redo names one direct
child. Applying a different move after undo creates a new retained branch. No action deletes or
rewrites an earlier event.

Pause changes session activity without changing marks or the active move. While paused, puzzle
changes and validation are rejected with corrective feedback; checkpoint creation and resume remain
available. A checkpoint uses a bounded, non-empty name and captures its move cursor, event position,
and state hash. Names are unique ignoring case. Restoring a checkpoint moves the active cursor and
reprojects marks while preserving every later event, so a subsequent move creates another retained
branch.

The complete event sequence is contiguous and SHA-256 chained. Each event records the resulting
move cursor and state hash. A session also carries separate hashes for its active state and complete
history. Replay recomputes every outcome from the original puzzle, attempt mode, and actions. It
rejects broken chains, altered outcomes, impossible cursor movement, and sessions that differ from
replay.

## Completion authority

A completion request passes the active assignment set to the independent Logic Grid final checker.
The session becomes completed only when that checker confirms completeness, fixed givens, category
bijections, and every normalized clue. Incomplete or incorrect attempts remain active. Completed
sessions retain later rejected actions but cannot change state.

## Public contract

`LogicGridPlaySession` is immutable and versioned as `1.1.0`. Its checked-in major-version schema is
`schemas/logic-grid-play-session-v1.schema.json`. The public service accepts in-memory typed values;
identifiers and checkpoint names are bounded by typed contracts, and no raw parser exceptions or
supplied source documents are retained. Each attempt is capped at 10,000 events so replay work and
retained history remain bounded during persistence and recovery.

## Deliberate exclusions

This play boundary does not provide clue-level mistake disclosure, hints, timers, storage policy,
learning inference, puzzle selection, filesystem behavior, terminal widgets, solve orchestration,
generation, reports, or telemetry. FAM-LG-009 consumes it for local persistence and descriptive
evidence without reinterpreting tentative marks as proof.
