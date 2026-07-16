# ADR-0008: Gate generation on deterministic evidence

## Status

Accepted

## Date

2026-07-16

## Owner

Repository owner

## Context

Future puzzle generators will combine construction recipes, solvers, human-rule traces, difficulty analysis, canonicalization, and novelty memory. A generator must not treat successful construction, a quality score, or a component's assertion as authority to publish a puzzle. It also needs reproducible lineage without making seed replay more authoritative than the final immutable artifact.

CR-007 requires a stable common boundary before any family generator is implemented.

## Decision

Represent generator intent, candidate lineage, evaluation evidence, quarantine, and terminal results as strict immutable contracts inside `deductra.generation`.

Candidate history uses a typed, zero-based, tamper-evident event chain. The final `PuzzleSpec` remains authoritative; lineage records generator, recipe, seed, random provider, dependencies, candidate ancestry, and accepted construction operations for audit and replay.

Uniqueness, difficulty, fingerprint, and novelty capabilities are ports. Their concrete algorithms and adapters remain outside CR-007. The acceptance function consumes their typed evidence and fails closed:

- proven hard-gate failures are rejected;
- unknown, conflicting, inconclusive, or incomplete evidence is quarantined;
- only fully verified candidates expose a playable puzzle.

No soft score, mode, recipe, or agent may override these gates.

## Alternatives considered

- Implement a complete generation coordinator immediately. Rejected because family construction and several evaluator algorithms are not part of this bounded packet.
- Let each family define unrelated result and lineage formats. Rejected because replay, quarantine, evidence, and publication safety are cross-family invariants.
- Treat every non-acceptance as rejection. Rejected because backend disagreement and incomplete proof must remain distinguishable from an ordinary bad candidate.
- Make the seed the authoritative artifact. Rejected because dependency and random-provider upgrades can change replay while the stored immutable puzzle remains valid.

## Consequences

Future generators receive one shared request, evidence, lineage, and terminal-result vocabulary. Normal play cannot receive rejected or quarantined puzzle payloads through this boundary. Lineage tampering and mismatched stream identity are detected before a result is valid.

The contracts intentionally do not prove the truth of an evidence provider. Future coordinator packets must bind these ports to authoritative verification, canonical human traces, calibrated difficulty logic, and durable novelty memory.

## Risks

The event vocabulary can grow if construction implementations add ad hoc events. New event types require a reviewed contract change. Typed evidence could also be fabricated by an untrusted caller; delivery layers must not expose the decision function as an unauthenticated authority boundary.

## Reconsideration triggers

Revisit this decision if a family cannot represent reproducible candidate ancestry, if authoritative evaluator evidence cannot fit the ports without losing proof detail, or if a migration requires versioned generation-contract coexistence.
