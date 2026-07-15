# ADR-0001: Use One Python Package for the Foundation

- Status: Accepted
- Date: 2026-07-15
- Owner: [@manurella](https://github.com/manurella)

## Context

Deductra is establishing one product and one release boundary. Its domain and public contracts are still being developed. Splitting the foundation into multiple packages or a workspace would add version coordination, publishing, dependency, and ownership costs before a demonstrated need exists.

## Decision

Use one repository, one Python distribution, one `src/deductra` import root, and one committed uv lockfile. Internal boundaries will be introduced within that package only when approved capabilities require them.

## Alternatives considered

- A workspace containing multiple independently configured packages.
- Multiple repositories with separately versioned distributions.
- A flat import layout without `src` isolation.

These alternatives add premature release boundaries or weaken installed-package testing without solving a current constraint.

## Consequences

- Cross-cutting changes remain atomic.
- Installation, compatibility testing, and release automation remain simple.
- Internal boundaries must be enforced through dependency rules and architecture tests rather than package publication boundaries.
- A future extraction will require an explicit compatibility and migration plan.

## Risks

Poorly governed internal imports could turn the package into an unstructured monolith. The mitigation is documented dependency direction, narrow public module surfaces, and automated architecture checks.

## Reconsideration triggers

Reconsider this decision when at least one condition is demonstrated:

- a component requires an independent release cadence;
- dependency sets or supported platforms materially conflict;
- installation size or startup cost requires an optional distribution;
- separate ownership or access control is required;
- independent deployment or failure isolation becomes necessary.

Any extraction proposal must identify consumers, compatibility guarantees, versioning, migration steps, release ownership, and rollback.
