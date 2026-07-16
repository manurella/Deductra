# ADR-0006: Separate human rule proposals from verification authority

- Status: Accepted
- Date: 2026-07-16
- Owner: [@manurella](https://github.com/manurella)

## Context

Human-style rules are needed for pedagogical discovery and canonical explanation order, but they are not independent proof. Registration order, timing metadata, an invalid rule, or an exhausted rule catalogue must not produce nondeterministic traces or hidden search.

## Decision

Define immutable rule, candidate, proposal, policy, attempt, and trace contracts in the reasoning boundary. Select candidates using total deterministic orders. Route every structurally valid proposal through a reasoning-owned authority port implemented by the verification package. Permit state reduction only when that adapter receives an accepted CR-004 verification decision.

End explicitly with `HUMAN_RULES_EXHAUSTED` when human discovery stalls. Search remains a separate future caller decision and is never invoked by this loop.

## Consequences

Family adapters can supply teaching rules without gaining proof authority. Invalid deductions are auditable and harmless, solver indeterminacy halts safely, and canonical logical traces exclude nondeterministic durations. The additional authority port prevents a dependency cycle between reasoning and verification.

No actual family rule catalogue or search behavior is included in this decision.

## Reconsideration triggers

Revisit the policy metrics when real family catalogues demonstrate that the current integer ranking evidence is insufficient, or when a new canonical trace version must include additional immutable evidence.
