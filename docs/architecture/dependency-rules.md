# Dependency Rules

Last reviewed: 2026-07-24

## Foundation rules

1. Production Python code lives under the single `src/deductra` import root.
2. Tests live outside the package and may depend on its public surface. Production code must not import from `tests`.
3. Repository validation belongs in `scripts` and must not become a runtime dependency.
4. Product code must not depend on CI, documentation, local tooling, or repository metadata.
5. Runtime dependencies must be declared in `project.dependencies`; development and security tools belong in named dependency groups.
6. Direct dependencies require review under the [project governance policy](../governance/project-governance.md).
7. Imports must not rely on undeclared packages, local machine paths, or optional tools that are absent from the selected installation profile.
8. The runtime image contains the installed package and its runtime dependencies only.

## Internal boundaries

Dependencies point from delivery mechanisms and integrations toward application policy, and from application policy toward domain policy. `deductra.domain` is the current innermost product boundary and remains independent of user-interface frameworks, persistence clients, solver backends, network protocols, report renderers, memory, and agents.

`deductra.reasoning` may depend on `deductra.domain` but not on persistence or higher layers. Its human loop depends on a reasoning-owned authority port rather than importing verification. `deductra.memory` owns common persistence ports and adapters and may depend on domain and reasoning contracts. Common SQLite details remain confined to `deductra.memory.sqlite_store`. The `deductra.memory.projections` subpackage may additionally consume generation fingerprint contracts but remains independent of solver backends, reports, interfaces, and agents. `deductra.verification` may depend on domain and reasoning contracts; solver-library imports, formulas, and the rule-authority adapter remain confined to verification. `deductra.graph` is a read-only projection boundary and may depend on domain and reasoning only. `deductra.generation` may depend on domain and reasoning contracts but must reach uniqueness, difficulty, fingerprint, and novelty implementations only through generation-owned ports. Family specifications and schema projections may depend only on common domain and family contracts. Family human-rule modules may additionally implement reasoning-owned contracts, but they may not import persistence, verification backends, generation, reports, agents, or delivery code. `deductra.agents` is an optional outer integration boundary that may consume domain, reasoning, and verification contracts; provider SDK loading stays confined to the provider adapter. No inner package may import agents or a concrete family. Domain and reasoning must not import memory, verification, graph projection, generation, families, reports, or agents.

```text
delivery and integrations -> application policy -> domain policy
```

`deductra.cli` is an outer delivery adapter. It may compose the concrete family, reasoning,
and verification boundaries, but no inner package may import it.

Family builder modules are outer application services rather than specification or human-rule
modules. A builder may compose its family contracts with reasoning and verification, but it may not
import delivery adapters, persistence, generation, reports, or agents. The stricter specification,
schema, rule, and solver boundaries remain unchanged.

Family assistance modules are also outer application services. They may compose play, human-rule,
and verification contracts to evaluate a move or derive evidence-backed disclosure. They may not
mutate play state, import persistence or delivery adapters, or establish authority without the
verification boundary.

Family structured-input modules sit at the same outer application boundary. They may consume a
family builder and an explicitly admitted parser, but parser types and exceptions must remain
inside the adapter. Structured input does not authorize filesystem, delivery, persistence,
generation, report, or agent dependencies.

Logic Grid attempt persistence is a reviewed family-specific outer adapter. Its typed attempt
contract may compose Logic Grid play, the family's sealed assistance evidence contracts, and common
memory projection contracts; its SQLite module may additionally depend on the standard-library
database driver. Neither module may be imported by the specification, play service, reasoning rules,
verification backends, assistance service, or common memory package. Persistence consumes only the
already cross-verified `LogicGridMoveEvaluation` document the assistance service returns; it never
imports the verification or reasoning boundaries the assistance service composes, and it never
re-verifies a stored evaluation. SQLite imports remain confined to this adapter and the common
canonical-event adapter. A shared interaction persistence framework is deferred until a second family
proves common semantics.

This direction is a constraint, not permission to create speculative layers. Until a capability exists, the corresponding package should not exist.

Cross-module imports must use an intentional public surface. Generic dumping grounds such as `common`, `helpers`, or `utils` require specific justification because they obscure ownership and dependency direction.

## Change threshold

A new architecture decision record is required when a change introduces or materially alters:

- a public API or serialized contract;
- a persistence or event boundary;
- an authentication or authorization model;
- a deployment unit or separately published package;
- a dependency-direction exception;
- a supported Python or platform boundary.

Architecture enforcement in `tests/architecture` translates these rules into mechanical checks. The current contracts cover the public path allowlist, single-package layout, CR-001 through CR-010, Logic Equations, Logic Grid, builder, structured-input, play, assistance, persistence, and SQLite-adapter boundaries, inward dependency direction, package metadata, Docker stage design, and production import roots. A check may be changed only with the governing documentation and decision record in the same reviewed change.
