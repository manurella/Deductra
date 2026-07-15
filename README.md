# Deductra

Deductra is an early-stage Python project for structured deductive-reasoning experiences. The repository is currently completing its M0 engineering foundation; it does not yet provide a puzzle engine, solver, generator, user interface, or stable public API.

## Foundation status

The current repository provides:

- a single typed `src/deductra` package supporting Python 3.13 and 3.14;
- locked development dependencies managed with uv;
- multi-stage development, test, artifact, and non-root runtime containers;
- pull-request quality, compatibility, Docker, documentation, and security checks;
- tag-driven wheel, source-distribution, GitHub Release, and GHCR publication.

Runtime dependencies remain intentionally empty during M0.

## Documentation

- [Contributor guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Project documentation](docs/README.md)
- [Architecture](docs/architecture/README.md)
- [Governance](docs/governance/README.md)

## Development

Install the locked environment and run the foundation checks:

```shell
uv sync --locked --all-groups
uv run pre-commit run --all-files
uv run pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete contribution contract.

## License

Deductra is available under the [MIT License](LICENSE).
