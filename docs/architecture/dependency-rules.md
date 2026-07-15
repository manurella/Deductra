# Dependency Rules

Last reviewed: 2026-07-15

## Foundation rules

1. Production Python code lives under the single `src/deductra` import root.
2. Tests live outside the package and may depend on its public surface. Production code must not import from `tests`.
3. Repository validation belongs in `scripts` and must not become a runtime dependency.
4. Product code must not depend on CI, documentation, local tooling, or repository metadata.
5. Runtime dependencies must be declared in `project.dependencies`; development and security tools belong in named dependency groups.
6. Direct dependencies require review under the [project governance policy](../governance/project-governance.md).
7. Imports must not rely on undeclared packages, local machine paths, or optional tools that are absent from the selected installation profile.
8. The runtime image contains the installed package and its runtime dependencies only.

## Future internal boundaries

When product modules are approved, dependencies should point from delivery mechanisms and integrations toward application policy, and from application policy toward domain policy. Domain policy must remain independent of user-interface frameworks, persistence clients, network protocols, and report renderers.

```text
delivery and integrations -> application policy -> domain policy
```

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

Architecture enforcement in `tests/architecture` translates these rules into mechanical checks. The current contracts cover the public path allowlist, single-package layout, M0 product boundary, package metadata, Docker stage design, and production import roots. A check may be changed only with the governing documentation and decision record in the same reviewed change.
