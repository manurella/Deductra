# ADR-0020: Cross-verify assistance before disclosure

## Status

Accepted

## Date

2026-07-20

## Owner

Repository owner

## Context

Logic Grid play deliberately records tentative marks without claiming correctness. Clue-aware
feedback and hints must therefore use proof authority without moving solver behavior into the pure
play reducer. Progressive assistance also needs to reveal useful information gradually while
retaining complete evidence for audit.

## Decision

Introduce a separate Logic Grid assistance application service. Evaluate a selected play atom and,
when necessary, its exact opposite through both independent family backends. Report logical support
or contradiction only from cross-verified certificates and fail closed otherwise.

Build hints from deterministic human-rule proposals over fixed facts plus individually verified
active marks. Store complete clue, premise, rule, conclusion, state, and certificate evidence once,
then derive a seven-level disclosure view from that immutable record. Withhold assistance in exam
mode. Return the highest-level action as a suggestion; do not mutate play or persistence inside the
assistance service.

## Alternatives considered

- Treat accepted play actions as correct. Rejected because reducer acceptance proves only a valid
  interaction transition.
- Compare moves with a stored final answer. Rejected because it provides no clue-level derivation
  and bypasses independent proof evidence.
- Use a solver-found move when human rules stall. Rejected because hints would conceal search and
  could not name a human technique.
- Put hint state inside the play session. Rejected because disclosure policy and proof composition
  are outer concerns and would enlarge the replay reducer.
- Apply the most explicit hint automatically. Rejected for this packet because mutation must remain
  an intentional play action with ordinary history and validation semantics.

## Consequences

Delivery layers can explain or correct a move with exact evidence while the play contract remains
presentation-neutral and tentative. Every hint level is traceable to one verified technique, and
backend uncertainty cannot become positive guidance. Cross-verifying active marks adds solver work,
but prevents one incorrect mark from contaminating later hints.

Assistance evidence is not yet durable. A later persistence integration may normalize evaluated
moves only if it preserves source-event identity, semantic hashes, certificates, and disclosure
separation.

## Risks

A presenter could expose fields beyond the selected disclosure view, or could apply a suggested
action without recording normal play history. Runtime verification cost may grow with large active
states. Mechanical disclosure tests, bounded puzzle contracts, explicit result statuses, and strict
adapter boundaries are the current mitigations.

## Reconsideration triggers

Revisit this decision when assistance is persisted, learning projections consume evaluated moves,
an interface applies suggested actions, measured verification cost requires caching, or another
puzzle family proves a stable shared assistance abstraction.
