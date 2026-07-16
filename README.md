# Deductra

Deductra is an early-stage Python project for structured, proof-carrying deductive reasoning. Its M0 engineering foundation and M1 common core are complete. M2 is validating that core with a typed Logic Equations specification, human-rule catalogue, and independent arithmetic proof encodings. The project does not yet provide parsing, final-solution and uniqueness checks, search, a concrete puzzle generator, a user interface, or a stable public API.

## Current status

The current repository provides:

- a single typed `src/deductra` package supporting Python 3.13 and 3.14;
- locked development dependencies managed with uv;
- multi-stage development, test, artifact, and non-root runtime containers;
- pull-request quality, compatibility, architecture, Docker, documentation, and security checks;
- tag-driven wheel, source-distribution, GitHub Release, and GHCR publication.
- strict, immutable domain models and a versioned JSON Schema for puzzle specifications.
- canonical lifecycle events with tamper-evident hash chains and transactional SQLite storage.
- deterministic immutable state reduction, replayable branches, and integrity-protected snapshots.
- source-bound proof obligations with independent Z3 and CP-SAT verification.
- deterministic human-rule discovery, selection, verified reduction, and explicit stalled traces.
- deterministic evidence-closed reasoning hypergraphs with visual-neutral JSON export.
- immutable generation requests, reproducible candidate lineage, evaluator ports, and fail-closed quarantine.
- deterministic attempt, learning-evidence, novelty, and artifact projections rebuilt from events.
- a validated finite-domain, all-different Logic Equations specification.
- deterministic Logic Equations human-rule discovery without hidden search.
- independently encoded Z3 and CP-SAT verification for Logic Equations deductions.

The admitted runtime dependencies and their rationale are recorded in the [dependency admissions](docs/governance/dependency-admissions.md).

## Documentation

- [Contributor guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Project documentation](docs/README.md)
- [Architecture](docs/architecture/README.md)
- [Governance](docs/governance/README.md)

## Development

Install the locked environment and run the project checks:

```shell
uv sync --locked --all-groups
uv run pre-commit run --all-files
uv run pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete contribution contract.

## License

Deductra is available under the [MIT License](LICENSE).
