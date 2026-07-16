# Current State

Last reviewed: 2026-07-16

Deductra has completed M0 and M1 and is beginning M2 with the Logic Equations reference kernel. The repository currently has:

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
- a typed optional AgentRuntime port, deterministic disabled mode, and isolated SDK adapter;
- fail-closed task, tool, evidence, hidden-search, solution-authority, and state-mutation guardrails;
- a fixed seven-case agent safety evaluation suite and checked-in AgentBoundary v1 JSON Schema.
- a typed Logic Equations specialization of the common immutable puzzle contract;
- validated `1..n` permutation-domain, all-different, expression, clue, and reference invariants;
- a checked-in Logic Equations Specification v1 JSON Schema.
- a deterministic six-technique Logic Equations human-rule catalogue;
- explainable single-variable constraint propagation and all-different proposals;
- canonical family-rule discovery without multi-variable enumeration or hidden search.
- independent symbolic Z3 and bounded CP-SAT encodings for Logic Equations expressions;
- explicit translation from internal domain codes to declared numeric values;
- cross-verified Logic Equations human-rule reduction through the common authority boundary.

CR-001 through CR-010 implement data, event, persistence, state projection, bounded verification, human-rule orchestration, deterministic hypergraph projection, generator-foundation contracts, rebuildable memory views, evidence-closed report derivation, and an optional non-authoritative agent boundary. FAM-LE-001 adds the first concrete family specification, FAM-LE-002 adds non-authoritative human-rule discovery, and FAM-LE-003 adds independent arithmetic proof encodings. Family rules never fall back to search and can change state only after accepted backend evidence. The hypergraph and memory indexes are read-only projections without authority over canonical history. Learning views contain descriptive evidence counts only. The generation boundary constructs no puzzles and contains no family logic, solver coordinator, difficulty algorithm, similarity algorithm, persistence, or playable queue. No parser, final-solution checker, solution enumerator, concrete generator, CLI, UI, report composer, named agent behavior, learning analyst, Golden puzzle, or stable public API exists. Report renderers, unverified family-rule proposals, and agent proposals do not decide canonical facts.

The owner accepted the M0 foundation after local and hosted CI verification. Branch protection and private vulnerability reporting were explicitly deferred by the owner and are not M1 or M2 blockers; this residual repository-administration risk remains recorded. FAM-LE-003 is the active implementation packet.
