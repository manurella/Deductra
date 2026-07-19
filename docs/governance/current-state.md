# Current State

Last reviewed: 2026-07-19

## Summary

Deductra is a pre-1.0 project. M0 established the professional engineering foundation, M1 established the family-neutral proof-carrying core, and M2 delivered the first deterministic Logic Equations reference kernel. M3, the complete Logic Grid product slice, is active.

The repository remains one Python distribution and one `deductra` import package. Version `1.0.0` is reserved for the fully completed and audited product defined in the [Product Roadmap](product-roadmap.md).

## Implemented capabilities

### Engineering foundation

- Python `>=3.13,<3.15`, uv-locked environments, and Hatchling packaging.
- Multi-stage development, test, CI-artifact, builder, and non-root runtime containers.
- Pull-request quality, typing, architecture, compatibility, documentation, Docker, and security automation.
- Tag-driven wheel, source-distribution, GitHub Release, and GHCR publication workflows.
- Contributor, security, governance, dependency-admission, and architecture contracts.
- An explicit public-path allowlist and enforced package/import boundaries.

### Proof-carrying common core

- Strict immutable puzzle specifications with canonical JSON and versioned schemas.
- Append-only lifecycle events, tamper-evident hash chains, transactional SQLite storage, and deterministic replay.
- Immutable puzzle-state reduction, retained contradiction branches, and non-authoritative snapshots.
- Source-bound proof obligations independently encoded for Z3 and CP-SAT.
- Fail-closed handling for invalid, unknown, or conflicting verification outcomes.
- Deterministic human-rule selection and verified reduction without hidden search.
- Evidence-closed reasoning hypergraphs, rebuildable memory projections, and renderer-neutral report models.
- Semantic local HTML plus standard, accessibility-targeted, and archival PDF derivation.
- An optional guarded agent runtime that cannot mutate canonical state or establish report facts.

### Logic Equations reference kernel

- A validated finite-domain permutation specification with family-specific JSON Schema.
- Six deterministic human-rule techniques with explainable, single-variable deductions.
- Independent symbolic Z3 and bounded CP-SAT encodings over declared numeric values.
- A fixed Golden Easy puzzle with dual-backend uniqueness evidence and an independent final checker.
- A verified CLI solve and write-once canonical HumanSolveTrace export.
- Cross-process and cross-platform trace identities that are independent of Python hash randomization and host set iteration.

### Logic Grid specification foundation

- An immutable category contract for unordered one-to-one associations.
- One stable item variable per visible item, aligned to a declared canonical anchor category.
- Exact category-size, variable-partition, item-label, anchor-mapping, and bijection invariants.
- Safe expression-tree support for direct, alternative, ordered, numeric-difference, cardinality, and compound clue semantics.
- Complete clue-constraint coverage and primary provenance validation.
- A checked-in Logic Grid Specification v1 JSON Schema with stable public identity.
- Five deterministic human-rule technique groups for association, category bijection, ordering, numeric relations, and compound clues.
- Explainable single-atom proposals with stable identities, exact source-state binding, and no hidden multi-variable search.

## Latest verification evidence

The 2026-07-19 verification pass completed successfully:

- local quality, formatting, typing, documentation, lockfile, and architecture checks passed;
- the local suite completed with 194 passing tests and three platform-specific PDF skips;
- the Docker test stage completed with 196 passing tests and one expected isolated-Git-index skip;
- the non-root runtime image ran the installed CLI without development tooling;
- Windows and Linux produced the same canonical Logic Equations trace identity.

Hosted workflow results are authoritative for pull requests and tagged publication. Local and container evidence does not replace those repository gates.

## Active milestone

M3 will deliver a complete Logic Grid vertical slice: formal family contracts, independent verification, deterministic human reasoning, three calibrated reference puzzles, guided and structured input, play and solve workflows, replay, local evidence, verified generation, difficulty and novelty evaluation, terminal interaction, and validated reports.

Implementation remains packet-based. FAM-LG-001 establishes the Logic Grid specification and validation boundary, and FAM-LG-002 adds non-authoritative human-rule semantics. Later M3 behavior must consume those boundaries and cannot bypass independent verification authority.

## Explicitly unavailable

The current repository does not yet provide user-authored puzzle input, a disclosed general search path, a concrete generator, a playable queue, an interactive interface, composed solve reports, a stable public Python API, complete learning behavior, named agent experiences, additional playable puzzle families, or release installers.

## Accepted administrative risk

Branch protection and private vulnerability reporting remain deferred by the repository owner. Until those controls are enabled, disciplined pull-request use and the published security contact are the active mitigations recorded in the [Risk Register](risk-register.md).
