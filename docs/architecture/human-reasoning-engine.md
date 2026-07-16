# Human Reasoning Engine

Last reviewed: 2026-07-16

CR-005 defines how deterministic human-style rules propose deductions without becoming proof authority. It adds interfaces and orchestration only; no puzzle-family rules, search solver, generator, interface, report system, memory projection, or agent behavior is implemented.

## Rule boundary

A `ReasoningRule` publishes a versioned `RuleReference`, discovers source-state-bound candidates, and converts a selected candidate into a non-authoritative `ProposedDeduction`. Discovery validates family scope, unique rule and candidate identities, exact source hashes, premises, affected variables, and supporting constraints. Results are canonically sorted, so registration order cannot change the solve trace.

The four selection policies are teaching-first, shortest-trace, maximum-information-gain, and family-canonical. Each policy uses a complete stable tie-break order. Information gain and pedagogical cost are integer evidence supplied by the rule; neither grants verification authority.

## Verified loop

The human loop discovers candidates, selects one, validates the proposal against the current state, creates a disclosed `human_rule` event, and sends the proposal and event through a `DeductionAuthority` port. The verification-side adapter constructs the proof obligation, invokes the independent backends, and applies the event only after an accepted decision.

Rejected proposals remain recorded but cannot change state. Inconclusive verification halts inconclusively, and backend disagreement halts in quarantine. If no untried human candidate remains, the trace ends with `HUMAN_RULES_EXHAUSTED`; the engine never opens a search branch or silently changes origin.

## Canonical trace

`HumanSolveTrace` records stable candidate, proposal, obligation, certificate, event, and state identities. Operational solver durations are intentionally excluded from this logical projection. Given the same puzzle, state, rules, policy, verification artifacts, and caller-provided event context, repeated runs produce byte-identical serialized traces and trace hashes.

The serialized contract is [Human Solve Trace v1](../../schemas/human-solve-trace-v1.schema.json). Full backend certificates remain governed by the separate verification record rather than being duplicated into the logical trace.

## Dependency direction

Reasoning owns the authority port; verification owns its adapter. This preserves the inward dependency direction: reasoning does not import solver packages or verification implementation, while verification may depend on reasoning contracts.
