# Deductra

Deductra is an early-stage Python project for structured, proof-carrying deductive reasoning. Its M0 engineering foundation is complete, and M1 begins with family-neutral immutable puzzle contracts. It does not yet provide a solver, generator, user interface, or stable public API.

## Current status

The current repository provides:

- a single typed `src/deductra` package supporting Python 3.13 and 3.14;
- locked development dependencies managed with uv;
- multi-stage development, test, artifact, and non-root runtime containers;
- pull-request quality, compatibility, architecture, Docker, documentation, and security checks;
- tag-driven wheel, source-distribution, GitHub Release, and GHCR publication.
- strict, immutable domain models and a versioned JSON Schema for puzzle specifications.
- canonical lifecycle events with tamper-evident hash chains and transactional SQLite storage.

Pydantic is the sole runtime dependency for M1's validated domain boundary.

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
