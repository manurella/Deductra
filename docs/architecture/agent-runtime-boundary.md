# Optional Agent Runtime Boundary

Last reviewed: 2026-07-16

Deductra's deterministic system remains complete when no agent runtime is configured. Agents are
optional proposal generators: they cannot mutate canonical state, verify deductions, commit
solutions, assign difficulty, or introduce unsupported report facts.

## Typed boundary

`AgentRuntime` accepts an `AgentRequest`, an expected `AgentOutput` subtype, and a minimal
`AgentContextView`. The context contains only named deterministic identities, evidence summaries,
verification status, and the effective tool allowlist. Every result records runtime, model, effort,
instruction version, requested and used tools, guardrail outcome, and canonical input/output
hashes.

`DisabledAgentRuntime` returns a typed `disabled` result without importing an SDK, reading
credentials, using tools, or accessing a network. Deterministic product workflows must select this
mode whenever remote enhancement is unavailable or disallowed.

## Authority and guardrails

Preflight validation rejects tasks and tools outside both the registered policy and the supplied
context. Post-output validation rejects:

- factual, solution, or report claims without evidence;
- unknown or unaccepted evidence;
- solution claims without deterministic backend verification;
- hidden search presented as reasoning;
- undeclared or non-allowlisted tool use;
- and commands that request canonical mutation or decision authority.

Rejected output is not returned to consumers. Its canonical hash remains in the audit result so a
future event adapter can record the rejection without retaining untrusted prose in authoritative
state.

## SDK adapter

The OpenAI Agents SDK is confined to `deductra.agents.openai_runtime`. Agent definitions and tool
bindings are registered explicitly; registered tools must exactly match the policy allowlist. The
adapter requests structured output, passes minimal typed context, and performs Deductra's own
guardrails after SDK execution.

Tracing is disabled by default. An application may opt in per registration, but sensitive model
and tool payload capture remains disabled. Credentials come from runtime configuration and are
never represented by Deductra contracts or repository files.

SDK exceptions produce typed failed results. They never trigger fabricated output or deterministic
fallback claims.

## Evaluation

The fixed evaluation suite covers ambiguous input, unsupported deductions, hidden search,
insufficient learning evidence, conflicting verifiers, verification-bypass attempts, and uncited
report claims. Passing these cases demonstrates boundary behavior, not model quality.
