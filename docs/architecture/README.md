# Architecture Documentation

Deductra begins as one Python distribution with one import root. Architecture is documented before it is expanded, and boundaries are introduced only when an approved capability requires them.

- [Foundation overview](overview.md) describes the current repository, package, build, and delivery architecture.
- [Core domain contracts](core-domain-contracts.md) defines the immutable CR-001 schema boundary.
- [Event protocol and store](event-protocol-and-store.md) defines CR-002 ordering, integrity, and persistence.
- [State reduction and replay](state-reduction-and-replay.md) defines CR-003 immutable projections, branch retention, and snapshots.
- [Verification contracts and backends](verification-contracts-and-backends.md) defines CR-004 proof obligations, independent encodings, certificates, and reducer authority.
- [Human reasoning engine](human-reasoning-engine.md) defines CR-005 rule discovery, deterministic policies, verified orchestration, and stalled outcomes.
- [Directed reasoning hypergraph](reasoning-hypergraph.md) defines CR-006 typed incidence projection, deterministic identifiers, evidence closure, and visual-neutral export.
- [Dependency rules](dependency-rules.md) defines the dependency direction that implementation and enforcement must preserve.
- [Architecture decisions](decisions/README.md) records significant decisions and their consequences.

These documents describe current accepted constraints. Undocumented future subsystems do not yet exist.

The executable contracts live in `tests/architecture`. They run in local hooks, the normal test suite, Docker's test stage, and the dedicated pull-request `Architecture` check.
