# Product Roadmap

Last reviewed: 2026-07-20

## Release principle

Deductra is developed through evidence-backed milestones, but a milestone is not the finished product. Version `1.0.0` is reserved for the complete, audited experience described by this roadmap. Until every completion gate is satisfied, project metadata and public communication must remain explicitly pre-1.0.

The roadmap defines sequence and exit evidence, not fixed dates. Only one bounded implementation packet is active at a time. Planned behavior must not be described as implemented, and shared abstractions are introduced only after concrete family implementations demonstrate the need.

## Milestone status

| Milestone | Outcome | Status |
| --- | --- | --- |
| M0 | Professional repository, packaging, container, CI, security, governance, and architecture foundation | Complete |
| M1 | Family-neutral proof-carrying reasoning core | Complete |
| M2 | Deterministic Logic Equations reference kernel | Complete |
| M3 | Complete Logic Grid product slice | Active |
| M4 | Shared product-platform extraction proven by two families | Planned |
| M5 | Remaining six puzzle families | Planned |
| M6 | Optional bounded agents and local learning experience | Planned |
| M7 | Complete Golden content and calibration corpus | Planned |
| M8 | Specials collections, synthesis puzzles, and final meta | Planned |
| M9 | Security, accessibility, performance, packaging, and release hardening | Planned |

## M3 — Logic Grid product slice

M3 turns the existing reasoning substrate into the first complete end-to-end user experience. It introduces the Logic Grid family, three calibrated reference puzzles, guided and structured input, play and solve workflows, replay, local progress evidence, verified generation, difficulty and novelty evaluation, terminal interaction, and standards-oriented reports.

M3 exits only when a user can provide or select a Logic Grid puzzle, interact with or solve it, obtain a verified trace, retain local evidence, and produce a validated report without an unverified subsystem becoming authoritative.

Implementation is proceeding through bounded family packets. FAM-LG-001 through FAM-LG-004
established the specification, human reasoning, independent verification, and calibrated references;
FAM-LG-005 added the guided authoring service; FAM-LG-006 added bounded JSON/YAML import and
deterministic export; and FAM-LG-007 added tentative play state, non-destructive undo/redo,
completion checking, and deterministic replay. FAM-LG-008 completes validation disclosure,
pause/resume, and named restorable checkpoints. FAM-LG-009 adds transactional local attempt
persistence, exact recovery, descriptive action evidence, and authoritative start/completion
projection. Clue-level evaluation, hints, generation, difficulty and novelty evaluation, terminal
delivery, and composed reports remain later M3 work.

## M4 — Proven common platform

After Logic Equations and Logic Grid both work, their genuinely shared generator coordination, difficulty evidence, canonicalization, novelty indexing, report components, terminal family boundary, and authoring tools are consolidated. This milestone removes demonstrated duplication; it does not anticipate later families speculatively.

## M5 — Family completion

The remaining families are implemented one at a time: ordered association, Sudoku, Greek Logic, Calcudoku, Kyudoku, and self-referential quizzes. Each family requires validated specifications, independent verification, human reasoning rules, three calibrated reference puzzles, generation, interaction, reporting, and regression evidence.

## M6 — Agents and learning

Optional agent and learning capabilities are integrated only after deterministic product paths are stable. Model output remains untrusted, evidence-cited, schema-validated, and unable to mutate canonical state or report facts. Equivalent deterministic workflows remain available without an external model service.

## M7 — Golden content

The reference corpus expands to three reviewed puzzles for every supported family. The corpus provides rule coverage, difficulty anchors, renderer fixtures, solver regressions, and reproducible portfolio evidence.

## M8 — Specials and synthesis

The authored collection adds three Specials per family, one synthesis puzzle per family collection, and a final cross-family meta. Mechanical correctness, accessibility, spoiler control, provenance, and blind playtesting are required; narrative presentation cannot conceal or alter formal rules.

## M9 — Release hardening

The release candidate undergoes full security, accessibility, performance, platform, packaging, content, report-conformance, and reproducibility audits. Installation and operation must be documented and repeatable on every declared Tier 1 platform.

## `1.0.0` completion gates

Deductra may use version `1.0.0` only when all of the following are verified:

1. All eight puzzle families support validated input, human reasoning, independent verification, and deterministic replay.
2. Play, Learn, Solve, Generate, Replay, and Report workflows are complete and accessible.
3. Generation proves uniqueness, enforces human-solvability policy, and records difficulty and novelty evidence.
4. Local memory and mastery projections rebuild exactly from canonical events.
5. Optional agents pass guardrail evaluations and cannot become a source of canonical truth.
6. Standard, accessibility-targeted, and archival reports pass their declared validation gates.
7. The complete Golden corpus, Specials collections, synthesis puzzles, and final meta are accepted.
8. Tier 1 platform, security, accessibility, performance, packaging, and reproducibility audits pass.
9. Public documentation accurately describes installation, operation, architecture, governance, supported behavior, and known limitations.

Progress toward these gates is recorded in [Current State](current-state.md). A gate is complete only when repository artifacts and executable evidence prove it.
