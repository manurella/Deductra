# Decision Log

Last reviewed: 2026-07-19

This log summarizes accepted project-level decisions. Architecturally significant decisions link to a detailed record containing context and consequences.

| ID | Decision | Status | Owner | Detailed record |
| --- | --- | --- | --- | --- |
| D-001 | Maintain one repository and one `src/deductra` distributable package. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0001](../architecture/decisions/0001-single-package-foundation.md) |
| D-002 | Support Python `>=3.13,<3.15`, with Python 3.14 as the development default. | Accepted | [@manurella](https://github.com/manurella) | [Foundation overview](../architecture/overview.md) |
| D-003 | Use uv with a committed lockfile and Hatchling as the build backend. | Accepted | [@manurella](https://github.com/manurella) | [Foundation overview](../architecture/overview.md) |
| D-004 | Keep M0 runtime dependencies empty. | Accepted | [@manurella](https://github.com/manurella) | [Dependency rules](../architecture/dependency-rules.md) |
| D-005 | Use multi-stage, non-root Docker images and BuildKit-aware builds. | Accepted | [@manurella](https://github.com/manurella) | [Foundation overview](../architecture/overview.md) |
| D-006 | Publish tagged wheels, source distributions, GitHub Releases, and GHCR images; do not publish to PyPI during M0. | Accepted | [@manurella](https://github.com/manurella) | [Project governance](project-governance.md) |
| D-007 | Require scoped Conventional Commits, immutable workflow action pins, and least-privilege automation. | Accepted | [@manurella](https://github.com/manurella) | [Project governance](project-governance.md) |
| D-008 | Enforce the public repository allowlist, single-package boundary, M0 dependency policy, Docker stages, and import roots with architecture tests. | Accepted | [@manurella](https://github.com/manurella) | [Dependency rules](../architecture/dependency-rules.md) |
| D-009 | Accept M0 after local and hosted CI verification; defer branch protection and private vulnerability reporting without blocking M1. | Accepted | [@manurella](https://github.com/manurella) | [Current state](current-state.md) |
| D-010 | Establish the immutable family-neutral domain schema and admit Pydantic as M1's first runtime dependency. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0002](../architecture/decisions/0002-common-core-schema.md) |
| D-011 | Store canonical lifecycle events in zero-based tamper-evident streams through a repository port and transactional SQLite adapter. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0003](../architecture/decisions/0003-canonical-event-store.md) |
| D-012 | Derive canonically hashed immutable state through pure reduction, retained branches, and non-authoritative snapshots. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0004](../architecture/decisions/0004-immutable-state-reduction.md) |
| D-013 | Authorize supported deductions only through source-bound obligations and fail-closed independent proof verification. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0005](../architecture/decisions/0005-independent-proof-verification.md) |
| D-014 | Keep human rules non-authoritative and run them through deterministic selection plus a verification-owned authority adapter. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0006](../architecture/decisions/0006-verified-human-reasoning-loop.md) |
| D-015 | Project immutable puzzle and reasoning sources into a deterministic evidence-closed directed hypergraph. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0007](../architecture/decisions/0007-project-reasoning-as-hypergraph.md) |
| D-016 | Gate generated candidates on deterministic evidence with reproducible lineage and fail-closed quarantine. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0008](../architecture/decisions/0008-gate-generation-on-deterministic-evidence.md) |
| D-017 | Treat attempt, learning, novelty, and artifact indexes as disposable event-derived projections. | Accepted | [@manurella](https://github.com/manurella) | [ADR-0009](../architecture/decisions/0009-derive-memory-views-from-events.md) |
| D-018 | Keep agents optional, typed, evidence-guarded, and without canonical authority. | Accepted | Repository owner | [ADR-0010](../architecture/decisions/0010-keep-agents-optional-and-non-authoritative.md) |
| D-019 | Specialize concrete families through validated common puzzle specifications. | Accepted | Repository owner | [ADR-0011](../architecture/decisions/0011-specialize-families-through-common-specifications.md) |
| D-020 | Keep Logic Equations human rules local, explainable, single-variable, and non-authoritative until independent family encodings exist. | Accepted | Repository owner | [Logic Equations human rules](../architecture/logic-equations-human-rules.md) |
| D-021 | Encode Logic Equations independently with symbolic Z3 formulas and bounded CP-SAT tables over declared numeric values. | Accepted | Repository owner | [ADR-0012](../architecture/decisions/0012-encode-logic-equations-independently.md) |
| D-022 | Reserve `1.0.0` for the complete product; intermediate milestones remain explicitly pre-1.0. | Accepted | Repository owner | [Product roadmap](product-roadmap.md) |
| D-023 | Represent Logic Grid categories as anchor-aligned item bijections over the common puzzle contract. | Accepted | Repository owner | [ADR-0013](../architecture/decisions/0013-model-logic-grid-as-anchor-aligned-bijections.md) |

New decisions receive the next sequential identifier. A superseding decision retains the old entry and links both records rather than erasing the earlier ruling.
