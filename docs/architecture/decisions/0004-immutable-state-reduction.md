# ADR-0004: Derive immutable state through retained branch projections

- Status: Accepted
- Date: 2026-07-16
- Owner: [@manurella](https://github.com/manurella)

## Context

Canonical events are durable evidence, but product capabilities need a current puzzle projection that is deterministic, immutable, and reconstructable. Contradiction reasoning also requires temporary branches without destructive rollback. Snapshots may accelerate replay but must not become an alternative source of truth.

## Decision

Represent each puzzle-branch projection as a canonically hashed immutable `PuzzleState`. Apply state-changing events through a pure reducer that requires event integrity, puzzle and branch identity, monotonic sequence, and the exact source-state hash.

Retain one lifecycle record and latest state for every opened branch. Closing a branch returns projection focus to its parent while preserving the child. Require explicit search origin for state mutations on search branches and reject search-origin mutations outside those branches.

Treat snapshots as integrity-protected copies tied to a source event. Event history remains authoritative and complete replay from genesis remains required.

## Consequences

Projection drift, stale writes, destructive rollback, and hidden search provenance fail explicitly. State and snapshot schemas become compatibility contracts. Replaying a long trace may be slower until snapshot persistence is introduced, but CR-003 avoids coupling the pure reducer to storage.

The reducer applies already-authorized state changes; it does not prove them. Proof obligations, verification certificates, and solver backends remain later packet work.
