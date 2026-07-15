# Contributing to Deductra

Thank you for helping build Deductra. The project is currently establishing its M0 engineering foundation. Contributions must remain within the approved change boundary and must not introduce product features prematurely.

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through the private process in [SECURITY.md](SECURITY.md), not through public issues.

## Development prerequisites

- Python 3.13 or 3.14
- [uv](https://docs.astral.sh/uv/)
- Docker with BuildKit for container validation
- Git

Create the locked development environment:

```shell
uv sync --locked --all-groups
```

## Propose a bounded change

Open a change proposal before substantial work. State:

- the objective and rationale;
- files expected to change;
- behavior that is deliberately out of scope;
- validation commands;
- risks and rollback.

Keep one coherent outcome per branch. Suggested branch names are:

```text
build/<short-description>
docs/<short-description>
feat/<short-description>
fix/<short-description>
refactor/<short-description>
```

## Public repository hygiene

Commit only polished project material. Credentials, private references, temporary notes, transcripts, generated planning material, local environments, caches, and build output belong outside the public history.

Do not commit a new direct dependency without documenting its purpose, maintenance status, license, platform support, alternatives, and removal strategy.

## Quality gates

Run the complete foundation checks before requesting review:

```shell
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python scripts/check_docs.py
uv build
docker buildx build --target test .
docker buildx build --target runtime .
```

Tests must exercise the installed `src/` package. Do not weaken checks, remove failing tests, or hide incomplete work behind broad exclusions.

## Commit messages

Use Conventional Commits with a required scope:

```text
type(scope): imperative subject
```

An optional change identifier may follow the subject:

```text
type(scope): imperative subject [PACKET-ID]
```

Allowed types are `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, and `test`. Use `!` before the colon for a breaking change and explain it in a `BREAKING CHANGE:` footer.

Examples:

```text
build(python): add locked development tooling
docs(contrib): clarify review requirements [EXEC-003]
```

Install the repository hooks after syncing:

```shell
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Pull requests

Pull requests must describe the objective, scope, evidence, architecture impact, risks, and rollback. Keep the branch current with `main`, resolve review conversations, and ensure every required check passes before merge.

Changes to a public contract or architectural boundary must update the relevant [governance](docs/governance/README.md), [architecture documentation](docs/architecture/README.md), or architecture decision record in the same pull request.

Do not begin a follow-on change merely because the current pull request is waiting for review.
