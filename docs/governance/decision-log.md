# Decision Log

Last reviewed: 2026-07-15

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

New decisions receive the next sequential identifier. A superseding decision retains the old entry and links both records rather than erasing the earlier ruling.
