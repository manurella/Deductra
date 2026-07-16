# ADR-0003: Persist canonical events in tamper-evident SQLite streams

- Status: Accepted
- Date: 2026-07-16
- Owner: [@manurella](https://github.com/manurella)

## Context

The common core needs deterministic replay and an audit trail before state reduction, verification, or puzzle-family behavior is introduced. Event ordering, causality, serialization, and integrity must be stable independently of a persistence technology. The first implementation must remain local-first, reproducible, and compatible with Python 3.13 and 3.14.

## Decision

Define immutable versioned event envelopes under `deductra.reasoning`. Seal each event with SHA-256 over canonical JSON and link it to the previous event hash. Treat every event at and after the first integrity failure as untrusted.

Define the append-only repository port under `deductra.memory` and implement it with Python's standard-library SQLite driver. Use strict tables, parameterized statements, explicit atomic append transactions, foreign keys, canonical JSON storage, indexed stream metadata, and WAL mode for file-backed databases. Begin stream sequence numbers at zero and use 64 zeroes as the genesis hash.

## Consequences

SQLite adds no runtime dependency, but the database schema and event envelope become versioned compatibility contracts. The adapter depends inward on reasoning events; reasoning does not import persistence. The current payload union is intentionally limited to lifecycle events. Later packets extend it alongside their semantics and tests.

The event store provides ordered replay input but not projected puzzle state. Deterministic state reduction and state replay remain CR-003 work.
