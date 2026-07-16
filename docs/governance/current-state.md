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
- immutable generator requests and candidate lineage with tamper-evident lifecycle events;
- typed uniqueness, difficulty, fingerprint, and novelty evaluator ports;
- a hard-gate decision that rejects proven failures and quarantines uncertainty;
- a checked-in GenerationContract v1 JSON Schema.
- hash-chained source events for disposable attempt, novelty, and artifact views;
- deterministic attempt and descriptive learning-evidence projections;
- rebuildable novelty-fingerprint and artifact-metadata indexes;
- a checked-in MemoryProjections v1 JSON Schema with clean-replay equivalence.
- an evidence-closed, renderer-neutral ReportModel with theme-isolated fact identity;
- semantic local-only HTML and protocol-isolated standard, accessible-target, and archival PDF derivation;
- hash-verified evidence attachments and a checked-in ReportModel v1 JSON Schema.

CR-001 through CR-009 implement data, event, persistence, state projection, bounded verification, human-rule orchestration, deterministic hypergraph projection, generator-foundation contracts, rebuildable memory views, and evidence-closed report derivation. The engine contains no concrete family rules and never falls back to search. The hypergraph and memory indexes are read-only projections without authority over canonical history. Learning views contain descriptive evidence counts only. The generation boundary constructs no puzzles and contains no family logic, solver coordinator, difficulty algorithm, similarity algorithm, persistence, or playable queue. No concrete generator, puzzle-family adapter, UI, report composer, learning analyst, agent runtime, or stable public API exists. Report contracts and renderers do not decide report content.

The owner accepted the M0 foundation after local and hosted CI verification. Branch protection and private vulnerability reporting were explicitly deferred by the owner and are not M1 blockers; this residual repository-administration risk remains recorded. CR-009 is the active implementation packet.
