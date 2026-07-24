# ADR-0022: Persist hint evidence into attempt memory

## Status

Accepted

## Date

2026-07-24

## Owner

Repository owner

## Context

FAM-LG-011 persisted cross-verified `LogicGridMoveEvaluation` documents and normalized their
decided outcomes into common `MoveEvaluated` memory, but explicitly stopped there: its ADR-0021
reconsideration triggers named "hint evidence also requires persistence" as the next open item, and
both the current-state and product-roadmap documents continued to state that hint requests and
their disclosure remain non-durable and outside common memory. The CR-008 schema has defined
`HintRevealed` and `StepExplained` payload events since M1, but no Logic Grid producer had ever
emitted either one; both projections stayed permanently empty regardless of how many hints a player
requested.

FAM-LG-010's `LogicGridHintResult` already carries a complete evidence-backed `LogicGridHint`, with
its own progressive `HintLevel` disclosure ladder, whenever a hint is available. That disclosure
ladder is the same mechanism risk R-021 relies on to stop assistance from leaking more evidence than
a player requested; any durable projection built from a hint result has to preserve that same
ladder rather than re-disclosing evidence the presentation layer withheld.

## Decision

Extend the FAM-LG-011 attempt adapter with a third, independent, hash-chained log —
`hint_results` — that durably retains already cross-verified `LogicGridHintResult` documents,
mirroring the existing `move_evaluations` log exactly: a new `record_hint_result` store operation,
independent of both `append` and `record_move_evaluation`, that never touches the play event stream
or the move-evaluation log, and that fails closed unless the result's attempt identity, puzzle
revision, and source session hash all match the attempt's current durable head.

Only `available` hint results normalize into common memory; every other `HintResultStatus`
(`correction_required`, `already_complete`, `unavailable_mode`, `human_rules_exhausted`,
`inconclusive`, `quarantined`) is stored for audit but never becomes a projection fact, matching the
FAM-LG-011 precedent for undecided move evaluations. An available result's own disclosure level
decides which shared event it becomes: a hint disclosed below `HintLevel.EXPLANATION` (levels 0
through 4) normalizes into `HintRevealed`, carrying the technique's `rule_id` only when the
disclosure ladder itself has already revealed the rule (from `HintLevel.TECHNIQUE` upward) and
`None` otherwise; a hint disclosed at `HintLevel.EXPLANATION` or `HintLevel.CONTINUE` normalizes
into `StepExplained`, which always carries the rule identity because the ladder requires it at that
level. No projection fact ever discloses a rule identity, premise, or conclusion the hint's own
disclosure had not already revealed to the caller.

Move evaluations and hint results are folded into one chronologically ordered projection sequence,
each still deduplicated within its own kind by content hash (`evaluation_hash` or `result_hash`) so
a repeated identical evaluation or hint request adds durable evidence without being double-counted.
Hint results observed at or after a session's completion time are stored but excluded from the
projection stream, preserving the same terminal-event invariant FAM-LG-011 already enforces. The
persisted contract becomes `1.2.0`.

## Alternatives considered

- Always disclose the technique's rule identity in `HintRevealed`, regardless of hint level.
  Rejected because it would let a common-memory consumer recover evidence a low-level hint
  deliberately withheld from the player, directly undermining the disclosure ladder ADR-0020 and
  risk R-021 depend on.
- Normalize every hint result status, including unavailable and blocked outcomes, into a shared
  event. Rejected for the same reason FAM-LG-011 excluded undecided move evaluations: the shared
  schema has no event for an unavailable or blocked request, and forcing one would misrepresent a
  withheld or blocked hint as delivered assistance.
- Give hint results their own separate projection stream instead of merging them into the existing
  attempt stream chronologically with move evaluations. Rejected because attempt projections are
  rebuilt as one ordered stream per attempt; a second sibling stream would require the rebuild
  command to merge two authorities instead of replaying one, without any offsetting benefit.

## Consequences

A cross-verified hint request now survives its originating call, and the common attempt and
learning projections receive real `HintRevealed` and `StepExplained` evidence instead of a
permanently empty count. Callers can request a hint, persist it, and later prove from storage alone
which disclosure level was granted and, where the ladder already revealed it, which rule was
applied. The attempt adapter gains one additional table and one additional store operation; the play
event stream and the move-evaluation log are unchanged.

## Risks

A caller could persist a hint result computed against a state the attempt no longer represents, or
replay an old result as if it were current; the same fail-closed source-session check FAM-LG-011
uses at write time, full record re-derivation and equality comparison on every read, and a dedicated
hash chain over the hint-result log are the current mitigations. A future change to the disclosure
ladder or to which fields `HintRevealed`/`StepExplained` may carry must preserve the invariant that a
projection fact never discloses more than the hint's own recorded level already revealed. Storage
grows with every recorded hint result, including duplicates and unavailable outcomes; no retention
policy exists yet.

## Reconsideration triggers

Revisit this decision when an interface applies a suggested hint action automatically, measured
storage growth requires retention or pruning, the hint disclosure ladder itself changes, or another
puzzle family proves a stable shared assistance-persistence abstraction.
