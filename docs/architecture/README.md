# Architecture Documentation

Deductra begins as one Python distribution with one import root. Architecture is documented before it is expanded, and boundaries are introduced only when an approved capability requires them.

- [Foundation overview](overview.md) describes the current repository, package, build, and delivery architecture.
- [Core domain contracts](core-domain-contracts.md) defines the immutable CR-001 schema boundary.
- [Event protocol and store](event-protocol-and-store.md) defines CR-002 ordering, integrity, and persistence.
- [State reduction and replay](state-reduction-and-replay.md) defines CR-003 immutable projections, branch retention, and snapshots.
- [Verification contracts and backends](verification-contracts-and-backends.md) defines CR-004 proof obligations, independent encodings, certificates, and reducer authority.
- [Human reasoning engine](human-reasoning-engine.md) defines CR-005 rule discovery, deterministic policies, verified orchestration, and stalled outcomes.
- [Directed reasoning hypergraph](reasoning-hypergraph.md) defines CR-006 typed incidence projection, deterministic identifiers, evidence closure, and visual-neutral export.
- [Generator foundation](generator-foundation.md) defines CR-007 requests, evidence ports, reproducible lineage, and fail-closed acceptance and quarantine contracts.
- [Event-sourced memory projections](event-sourced-memory-projections.md) defines CR-008 attempt, learning-evidence, novelty, and artifact views with exact replay rebuilds.
- [Report contract and rendering](report-contract-and-rendering.md) defines CR-009 evidence closure, theme isolation, semantic HTML, and protocol-isolated PDF derivation.
- [Optional agent runtime boundary](agent-runtime-boundary.md) defines CR-010 typed proposals, tool allowlists, guardrails, offline mode, and the isolated SDK adapter.
- [Logic Equations specification](logic-equations-specification.md) defines FAM-LE-001's finite-domain arithmetic-assignment shape and validation boundary.
- [Logic Equations human rules](logic-equations-human-rules.md) defines FAM-LE-002's deterministic technique catalogue, local propagation, and verification boundary.
- [Logic Equations backend encodings](logic-equations-backend-encodings.md) defines FAM-LE-003's numeric semantics, independent Z3 and CP-SAT translations, and fail-closed limits.
- [Logic Equations CLI and trace delivery](logic-equations-cli-and-trace.md) defines FAM-LE-005's verified Golden solve and deterministic trace-export boundary.
- [Logic Grid specification](logic-grid-specification.md) defines FAM-LG-001's anchor-aligned category bijections and validation boundary.
- [Logic Grid human rules](logic-grid-human-rules.md) defines FAM-LG-002's deterministic association, bijection, ordered, numeric, and compound clue techniques.
- [Dependency rules](dependency-rules.md) defines the dependency direction that implementation and enforcement must preserve.
- [Architecture decisions](decisions/README.md) records significant decisions and their consequences.

These documents describe current accepted constraints. Undocumented future subsystems do not yet exist.

The executable contracts live in `tests/architecture`. They run in local hooks, the normal test suite, Docker's test stage, and the dedicated pull-request `Architecture` check.
