# Architecture Overview

Last reviewed: 2026-07-19

## Current system boundary

Deductra is one repository, one Python distribution, and one `deductra` import package. The current pre-1.0 system includes immutable puzzle contracts, event-sourced state, independently verified deductions, deterministic human reasoning, derived memory and graph projections, report renderers, an optional guarded agent boundary, and the first Logic Equations family kernel. It does not yet expose a stable public API.

```text
repository
├── src/deductra/     single Python distribution
├── schemas/          versioned external contracts
├── tests/            behavior and architecture verification
├── docs/             canonical public documentation
├── scripts/          repository validation
└── .github/          review, security, and release automation
```

The single-package decision keeps changes atomic and avoids release, dependency, and ownership machinery that the project does not yet need. [ADR-0001](decisions/0001-single-package-foundation.md) records the rationale and reconsideration triggers.

## Python and packaging

The package supports Python `>=3.13,<3.15`. Python 3.14 is the default development and container runtime; CI also tests Python 3.13.

uv manages and locks all dependency profiles. Hatchling builds the wheel and source distribution. Direct runtime dependencies are admitted individually with a documented purpose, compatibility evidence, operational cost, and removal strategy. The canonical record is [Runtime Dependency Admissions](../governance/dependency-admissions.md).

## Runtime architecture

Dependency direction is inward toward immutable domain contracts. Reasoning proposes and reduces state transitions; verification alone authorizes supported deductions. Graphs, memory views, reports, and agent-facing results are downstream projections and cannot mutate canonical truth. Family packages specialize the shared contracts without bypassing verification authority.

The current CLI exercises this architecture through one fixed Logic Equations puzzle. Planned product surfaces remain pre-1.0 roadmap work until their contracts, implementation, and acceptance evidence are committed.

## Container architecture

The Dockerfile separates concerns through named stages:

| Stage | Responsibility |
| --- | --- |
| `uv` | Supplies the pinned uv binaries. |
| `python-base` | Provides shared development and build configuration. |
| `development` | Installs locked development tools and project sources. |
| `test` | Runs formatting, linting, typing, tests, and package builds. |
| `ci-report-builder` | Produces machine-readable test and coverage artifacts. |
| `ci-report` | Exposes CI artifacts without creating a product-reporting name collision. |
| `builder` | Installs only the project and runtime dependency set. |
| `runtime` | Runs the installed package as an unprivileged user. |

The runtime stage starts from a clean slim Python image rather than inheriting the development image. Build tools and audit dependencies therefore remain outside the runtime image.

## Delivery architecture

Pull requests run commit-policy, formatting, linting, typing, documentation, Python compatibility, Docker, dependency, workflow, and CodeQL checks. Workflow permissions default to read-only and are elevated only within publication or security-analysis jobs.

Version tags build a wheel and source distribution, verify the wheel on Python 3.13 and 3.14, create a GitHub Release, publish the runtime image to GHCR, and attest both artifact classes. Container ownership is derived from repository context rather than a hardcoded account.

## Evolution rule

New internal modules must represent an approved capability and follow [dependency rules](dependency-rules.md). A module is not created merely to reserve a name or anticipate possible scale. Shared abstractions are extracted only after at least two concrete implementations establish stable semantics. Expensive-to-reverse changes to topology, public contracts, persistence, security, or distribution require a new architecture decision record.
