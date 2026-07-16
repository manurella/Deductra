# ADR-0010: Keep agents optional and non-authoritative

## Status

Accepted

## Date

2026-07-16

## Owner

Repository owner

## Context

Agent assistance can help interpret requests, explain deterministic results, and propose typed
actions. Model output is probabilistic, may cite nonexistent evidence, and may attempt actions
outside its task. Allowing an SDK or model response to become canonical authority would break the
project's proof-carrying guarantees and offline completeness.

CR-010 also requires an initial SDK adapter without coupling domain, reasoning, verification,
memory, generation, graph, or report packages to provider types.

## Decision

Define a Deductra-owned asynchronous `AgentRuntime` port with strict typed requests, context,
outputs, audit results, and guardrail reports.

Treat every agent result as a proposal. Validate task and tool scope before execution, then validate
evidence closure, deterministic verification, declared tool use, hidden search, and authority
boundaries after execution. Do not expose rejected output to downstream consumers.

Provide a deterministic disabled runtime as the default offline behavior. Isolate the exactly
locked OpenAI Agents SDK in one adapter. Disable tracing by default and exclude sensitive payloads
even when tracing is explicitly enabled.

## Alternatives considered

- Allow agents to append domain events directly. Rejected because probabilistic output cannot grant
  itself deterministic authority.
- Depend on SDK guardrails alone. Rejected because Deductra's evidence and authority laws must
  remain provider-independent and testable offline.
- Make remote agents mandatory. Rejected because puzzle correctness and all deterministic workflows
  must remain available without credentials or network access.
- Defer the adapter while defining only a protocol. Rejected because CR-010 explicitly requires one
  real integration boundary and its compatibility evidence.

## Consequences

Core packages remain independent of the SDK and network. Applications can disable agents without
losing deterministic behavior. Every accepted proposal has explicit evidence and tool provenance.

The SDK adds a substantial transitive dependency graph and an external API integration surface.
Applications must separately own credentials, rate limits, model registration, privacy policy,
retention choices, and operational monitoring.

## Risks

An allowlisted tool may still contain a defective implementation; tool registration does not prove
tool correctness. Model and SDK behavior can change between versions, so the SDK is exactly pinned
and adapter tests must run before upgrades. The current audit result is typed but is not yet
persisted as an event.

## Reconsideration triggers

Revisit this decision if a provider cannot preserve structured outputs, if SDK upgrades break the
runtime port, if tracing policy changes, or if a deterministic local assistant can replace the
remote enhancement without weakening the contract.
