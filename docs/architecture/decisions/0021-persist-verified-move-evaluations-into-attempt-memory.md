# ADR-0021: Persist verified move evaluations into attempt memory

## Status

Accepted

## Date

2026-07-24

## Owner

Repository owner

## Context

FAM-LG-010 introduced a separate assistance service that cross-verifies one submitted play atom
and, when necessary, its exact opposite, before classifying a move as supported, contradicted,
inconclusive, or quarantined. ADR-0020 deliberately left that evidence non-durable: the assistance
service may not mutate play or persistence, and the FAM-LG-009 attempt adapter normalized only
`AttemptStarted` and independently verified `AttemptCompleted` facts into common memory, reporting
zero evaluated moves regardless of play activity.

That boundary is now the last open item named by both records. The product roadmap and current
state document explicitly withhold "persist assistance evidence" and "normalize evaluated moves
into learning projections" as outstanding FAM-LG-010 follow-on work. Without it, the CR-008
`MoveEvaluated` and rule-evidence projections the common memory schema already defines stay
permanently empty for Logic Grid, and no durable record of a cross-verified move survives beyond
one request.

## Decision

Extend the FAM-LG-009 attempt adapter, not the assistance service, to durably retain already
cross-verified `LogicGridMoveEvaluation` documents and fold only their decided outcomes into common
memory.

`PersistedLogicGridAttempt` gains an ordered, hash-chained `move_evaluations` log alongside its
existing play `observations`. Each entry pairs one sealed evaluation with a local observation time
and a predecessor hash, mirroring the existing play-observation pattern. Recording an evaluation is
a new store operation, `record_move_evaluation`, independent of `append`: it never touches the play
event stream, and it fails closed unless the evaluation's attempt identity, puzzle revision, source
event, and source session hash all match the attempt's current durable head.

Only `supported` and `contradicted` evaluations normalize into `MoveEvaluated` projection events,
each fingerprinted by the evaluation's own content hash so a repeated identical evaluation is
retained as additional evidence without being double-counted. `inconclusive` and `quarantined`
evaluations are stored for audit but never become a projection fact, matching the existing
descriptive-evidence precedent that already retains rejected play actions without granting them
authority. Evaluations observed at or after a session's completion time are stored but excluded from
the projection stream, preserving the CR-008 invariant that no attempt stream carries an event after
its terminal fact. The technique's rule identity, when a verified technique produced the evaluation,
becomes the projection's `rule_id`; the shared `MoveEvaluated.duration_ms` field, which this
integration does not measure, is fixed at zero rather than approximated. The persisted contract
becomes `1.1.0`, following the same additive versioning FAM-LG-008 already used for the play session
contract.

## Alternatives considered

- Persist assistance evidence from inside the assistance service. Rejected because ADR-0020 already
  forbids the assistance boundary from importing persistence, and mixing proof composition with
  durability would re-couple two independently reviewed outer adapters in one direction only.
- Re-verify every stored evaluation on read, the way play events are fully replayed. Rejected because
  cross-verification invokes both solver backends; repeating it on every read would make attempt
  reads solver-bound and defeats the purpose of capturing dual-backend proof once.
- Normalize every evaluation status, including inconclusive and quarantined outcomes, into
  `MoveEvaluated`. Rejected because the shared event only distinguishes `accepted` and `rejected`,
  and forcing an undecided result into either value would misrepresent verification uncertainty as a
  decided outcome.
- Approximate `duration_ms` from certificate solve time or wall-clock request latency. Rejected
  because FAM-LG-009 already excludes timers and elapsed-time claims from this family, and certificate
  duration is deliberately excluded from assistance evidence identity.

## Consequences

A cross-verified move evaluation now survives its originating request, and the common attempt and
learning projections finally receive real Logic Grid evidence instead of a permanently empty count.
Callers can request an evaluation, persist it, and later prove from storage alone that one specific
atom was independently supported or contradicted, with its full technique and certificate evidence
intact. The attempt adapter gains one additional table and one additional store operation; the play
event stream, its schema, and its replay contract are unchanged.

## Risks

A caller could persist an evaluation computed against a state the attempt no longer represents, or
replay old evidence as if it were current. Fail-closed source-session and source-event checks at
write time, full record re-derivation and equality comparison on every read, and a dedicated hash
chain over the evaluation log are the current mitigations. Storage grows with every recorded
evaluation, including duplicates; no retention policy exists yet.

## Reconsideration triggers

Revisit this decision when hint evidence also requires persistence, an interface applies a suggested
action automatically, measured storage growth requires retention or pruning, or another puzzle
family proves a stable shared assistance-persistence abstraction.
