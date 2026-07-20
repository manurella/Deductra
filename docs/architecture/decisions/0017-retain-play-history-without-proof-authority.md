# ADR-0017: Retain play history without granting proof authority

## Status

Accepted

## Context

Logic Grid interaction needs tentative cell marks, undo, redo, completion, and deterministic replay.
The common reasoning state contains verified deductions and explicit proof provenance, so using it
for guesses or personal notes would falsely elevate user input. Destructive undo would also erase
evidence and make branched attempts impossible to reproduce.

## Decision

Add a family-specific, presentation-neutral play-session application service. Keep tentative
assignments and exclusions separate from verified reasoning state. Retain every accepted and
rejected action in a versioned hash chain, model accepted cell actions as a parent-linked move
graph, and implement undo and redo by moving an active cursor rather than deleting history.

Derive the complete session from the immutable puzzle plus its event sequence. Fail when a supplied
session differs from deterministic replay. Delegate terminal completion authority to the existing
independent final checker; ordinary marks never assert proof.

## Consequences

- Presentation adapters receive deterministic marks, control outcomes, and replay evidence without
  owning domain state.
- Undo followed by a different move preserves both branches and requires an explicit redo target
  when more than one path exists.
- Rejected actions are auditable but do not mutate active marks.
- The play-session schema becomes a compatibility contract.
- Persistence, validation modes, hints, checkpoints, timers, learning evidence, and UI behavior
  remain separate work.
