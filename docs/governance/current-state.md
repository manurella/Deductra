# Current State

Last reviewed: 2026-07-16

Deductra has completed M0 and is beginning M1, the common proof-carrying core. The repository currently has:

- a clean public scaffold and repository-hygiene policy;
- one typed `src/deductra` package with reviewed, locked runtime dependencies;
- Python 3.13 and 3.14 compatibility;
- a uv lockfile and Hatchling build configuration;
- development, test, CI-artifact, builder, and non-root runtime container stages;
- contributor, commit, pull-request, conduct, and security contracts;
- pull-request CI, scheduled security checks, tag-driven GitHub Releases, and GHCR publication;
- canonical public governance and architecture documentation;
- automated repository, package, import, dependency, and Docker architecture contracts;
- strict immutable puzzle-domain models, canonical serialization, and a checked-in PuzzleSpec v1 JSON Schema;
- immutable lifecycle-event envelopes, deterministic hash-chain verification, and a checked-in EventEnvelope v1 JSON Schema;
- an append-only event-store port and transactional SQLite adapter;
- immutable PuzzleState projections, pure deterministic reduction, retained contradiction branches, replay, and integrity-protected snapshots;
- a checked-in PuzzleState v1 JSON Schema;
- source-bound assignment and elimination proof obligations;
- independent Z3 and CP-SAT encodings with sealed verification certificates;
- fail-closed inconclusive and quarantine outcomes plus a verified reducer boundary;
- a checked-in VerificationRecord v1 JSON Schema;
- family-neutral human-rule, application-candidate, and proposed-deduction interfaces;
- deterministic teaching, shortest-trace, information-gain, and family-canonical policies;
- a verified human solve loop with explicit stalled, inconclusive, and quarantined outcomes;
- a checked-in HumanSolveTrace v1 JSON Schema;
- a typed directed incidence hypergraph projected from immutable puzzle and trace sources;
- stable graph identifiers, evidence-closure enforcement, and visual-neutral canonical JSON;
- a checked-in ReasoningHypergraph v1 JSON Schema.

CR-001 through CR-006 implement data, event, persistence, state-projection, bounded verification, human-rule orchestration, and deterministic hypergraph-projection contracts. The engine contains no concrete family rules and never falls back to search. The hypergraph is read-only and contains no layout or presentation authority. No generator, puzzle-family adapter, UI, report system, learning memory, agent runtime, or stable public API exists.

The owner accepted the M0 foundation after local and hosted CI verification. Branch protection and private vulnerability reporting were explicitly deferred by the owner and are not M1 blockers; this residual repository-administration risk remains recorded. CR-006 is the active implementation packet.
