# Current State

Last reviewed: 2026-07-20

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

### Logic Grid verified reasoning foundation

- An immutable category contract for unordered one-to-one associations.
- One stable item variable per visible item, aligned to a declared canonical anchor category.
- Exact category-size, variable-partition, item-label, anchor-mapping, and bijection invariants.
- Safe expression-tree support for direct, alternative, ordered, numeric-difference, cardinality, and compound clue semantics.
- Complete clue-constraint coverage and primary provenance validation.
- A checked-in Logic Grid Specification v1 JSON Schema with stable public identity.
- Five deterministic human-rule technique groups for association, category bijection, ordering, numeric relations, and compound clues.
- Explainable single-atom proposals with stable identities, exact source-state binding, and no hidden multi-variable search.
- Independent symbolic Z3 and bounded CP-SAT encodings for every normalized Logic Grid clue form.
- Explicit separation of anchor-row identity, ordinal order, and exact integer or rational numeric meaning.
- Cross-verified human-rule reduction with fail-closed counterexample, inconsistency, resource-limit, timeout, and disagreement behavior.
- An original reference triad: 3x3 Easy, 4x4 Medium, and 5x5 Hard.
- An independent final checker covering completeness, givens, bijections, and every normalized clue form.
- Dual-backend satisfiability and assignment-entailment evidence proving each reference solution is unique.
- Deterministic verified human solves and fixed canonical content hashes for all three references.
- An immutable, incomplete-safe Logic Grid guided-draft contract with a checked-in v1 JSON Schema.
- Staged category, clue, preview, proof, and ready assessments with field-scoped corrective messages.
- Composable guided templates covering every normalized Logic Grid Boolean and numeric clue form.
- Deterministic compilation into the canonical Logic Grid specification with generated natural-language and association-grid previews.
- A fail-closed readiness gate that requires dual-backend human-rule completion and independent final checking without hidden search.
- Bounded, explicit JSON and restricted-YAML import into the same immutable guided-draft contract.
- Sanitized syntax, resource, and schema errors with stable codes, precise paths, corrective actions, and source locations where available.
- Deterministic canonical JSON and human-readable alias-free YAML exports with cross-format semantic parity.
- A checked-in Logic Grid Structured Import Result v1 JSON Schema and an exact PyYAML runtime admission.
- An immutable Logic Grid play session with tentative assignments, exclusions, and fixed-given protection.
- Parent-linked move history with non-destructive undo, explicit redo, retained branches, and rejected-action evidence.
- Independent final-checker completion authority, exact full-history replay, and a checked-in Play Session v1 JSON Schema.

## Latest verification evidence

The 2026-07-20 verification pass completed successfully:

- local quality, formatting, typing, documentation, lockfile, and architecture checks passed;
- the local suite completed with 264 passing tests and three platform-specific PDF skips;
- the Docker test stage completed with 266 passing tests and one expected isolated-Git-index skip;
- the non-root runtime image ran the installed CLI without development tooling;
- the non-root runtime image imported PyYAML 6.0.3 and the structured-input public surface as UID 10001;
- the Logic Grid play-session corpus passed identically on Windows and Linux, including retained branching replay and tamper rejection;
- Windows and Linux produced the same canonical Logic Equations trace identity.

Hosted workflow results are authoritative for pull requests and tagged publication. Local and container evidence does not replace those repository gates.

## Active milestone

M3 will deliver a complete Logic Grid vertical slice: formal family contracts, independent verification, deterministic human reasoning, three calibrated reference puzzles, guided and structured input, play and solve workflows, replay, local evidence, verified generation, difficulty and novelty evaluation, terminal interaction, and validated reports.

Implementation remains packet-based. FAM-LG-001 through FAM-LG-006 establish specification,
reasoning, verification, references, guided authoring, and structured input. FAM-LG-007 adds the
presentation-neutral play and replay boundary while keeping tentative marks outside proof authority.
Later M3 behavior must consume these boundaries and cannot bypass cross-verification.

## Explicitly unavailable

The current repository does not yet provide validation modes, hints, play persistence, an interactive
or filesystem authoring adapter, a disclosed general search path, a concrete generator, a playable
queue, an interactive interface, composed solve reports, a stable cross-family public Python API,
complete learning behavior, named agent experiences, additional playable puzzle families, or
release installers.

## Accepted administrative risk

Branch protection and private vulnerability reporting remain deferred by the repository owner. Until those controls are enabled, disciplined pull-request use and the published security contact are the active mitigations recorded in the [Risk Register](risk-register.md).
