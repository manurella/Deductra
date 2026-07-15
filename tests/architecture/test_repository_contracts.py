"""Enforce the repository, packaging, and container foundation contracts."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_PATH_ALLOWLIST = frozenset(
    {
        ".dockerignore",
        ".editorconfig",
        ".gitattributes",
        ".github/CODEOWNERS",
        ".github/ISSUE_TEMPLATE/change-proposal.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/dependabot.yml",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
        ".github/workflows/security.yml",
        ".gitignore",
        ".pre-commit-config.yaml",
        ".python-version",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "Dockerfile",
        "LICENSE",
        "README.md",
        "SECURITY.md",
        "docs/README.md",
        "docs/architecture/README.md",
        "docs/architecture/core-domain-contracts.md",
        "docs/architecture/decisions/0002-common-core-schema.md",
        "docs/architecture/decisions/0001-single-package-foundation.md",
        "docs/architecture/decisions/README.md",
        "docs/architecture/dependency-rules.md",
        "docs/architecture/overview.md",
        "docs/governance/README.md",
        "docs/governance/current-state.md",
        "docs/governance/decision-log.md",
        "docs/governance/project-governance.md",
        "docs/governance/risk-register.md",
        "pyproject.toml",
        "schemas/puzzle-spec-v1.schema.json",
        "scripts/check_conventions.py",
        "scripts/check_docs.py",
        "scripts/export_json_schema.py",
        "src/deductra/__init__.py",
        "src/deductra/domain/__init__.py",
        "src/deductra/domain/atoms.py",
        "src/deductra/domain/base.py",
        "src/deductra/domain/constraints.py",
        "src/deductra/domain/expressions.py",
        "src/deductra/domain/ids.py",
        "src/deductra/domain/puzzle.py",
        "src/deductra/domain/schema.py",
        "src/deductra/domain/serialization.py",
        "src/deductra/domain/values.py",
        "src/deductra/py.typed",
        "tests/architecture/test_import_boundaries.py",
        "tests/architecture/test_repository_contracts.py",
        "tests/domain/test_core_schema.py",
        "tests/test_package.py",
        "uv.lock",
    }
)
REQUIRED_FOUNDATION_PATHS = frozenset(
    {
        "Dockerfile",
        "README.md",
        "docs/architecture/dependency-rules.md",
        "docs/governance/project-governance.md",
        "pyproject.toml",
        "src/deductra/__init__.py",
        "src/deductra/py.typed",
        "tests/architecture/test_import_boundaries.py",
        "tests/architecture/test_repository_contracts.py",
        "uv.lock",
    }
)
EXPECTED_DOCKER_STAGES = (
    "uv",
    "python-base",
    "development",
    "test",
    "ci-report-builder",
    "ci-report",
    "builder",
    "runtime",
)


def tracked_paths() -> set[str]:
    """Return normalized paths currently present in the public Git index."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return {path.decode("utf-8").replace("\\", "/") for path in result.stdout.split(b"\0") if path}


def project_configuration() -> dict[str, Any]:
    """Read the canonical project metadata."""
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as project_file:
        return tomllib.load(project_file)


def unexpected_public_paths(paths: set[str]) -> set[str]:
    """Return tracked paths that are outside the explicit public contract."""
    return paths - PUBLIC_PATH_ALLOWLIST


def test_public_index_contains_only_allowlisted_paths() -> None:
    """Reject unexpected tracked artifacts unless the public contract is updated."""
    if not (REPOSITORY_ROOT / ".git").exists():
        pytest.skip("public Git index is unavailable in the isolated container test context")
    unexpected = unexpected_public_paths(tracked_paths())
    assert not unexpected, f"unexpected tracked paths: {sorted(unexpected)}"


def test_public_allowlist_rejects_an_unregistered_path() -> None:
    """Prove that an arbitrary tracked artifact is outside the public contract."""
    assert unexpected_public_paths({"notes.md"}) == {"notes.md"}


def test_required_foundation_paths_exist() -> None:
    """Keep the minimum public architecture and validation surface present."""
    missing = {path for path in REQUIRED_FOUNDATION_PATHS if not (REPOSITORY_ROOT / path).is_file()}
    assert not missing, f"missing foundation paths: {sorted(missing)}"


def test_source_tree_has_one_distribution_package() -> None:
    """Prevent a premature workspace or second import root."""
    source_root = REPOSITORY_ROOT / "src"
    packages = sorted(
        path.name for path in source_root.iterdir() if path.is_dir() and path.name != "__pycache__"
    )
    assert packages == ["deductra"]


def test_m1_package_contains_only_approved_core_schema_modules() -> None:
    """Keep CR-001 limited to the approved domain schema surface."""
    package_root = REPOSITORY_ROOT / "src" / "deductra"
    public_files = {
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert public_files == {
        "__init__.py",
        "domain/__init__.py",
        "domain/atoms.py",
        "domain/base.py",
        "domain/constraints.py",
        "domain/expressions.py",
        "domain/ids.py",
        "domain/puzzle.py",
        "domain/schema.py",
        "domain/serialization.py",
        "domain/values.py",
        "py.typed",
    }


def test_project_metadata_preserves_package_boundaries() -> None:
    """Enforce the accepted package, Python, build, and dependency policy."""
    configuration = project_configuration()
    project = cast(dict[str, Any], configuration["project"])
    build_system = cast(dict[str, Any], configuration["build-system"])
    hatch = cast(dict[str, Any], configuration["tool"])["hatch"]

    assert project["name"] == "deductra"
    assert project["requires-python"] == ">=3.13,<3.15"
    assert project["dependencies"] == ["pydantic>=2.13,<3"]
    assert build_system["build-backend"] == "hatchling.build"
    assert hatch["build"]["targets"]["wheel"]["packages"] == ["src/deductra"]


def test_dockerfile_preserves_named_stage_contract() -> None:
    """Keep development, validation, artifact, build, and runtime stages distinct."""
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
    stages = tuple(
        match.group(1)
        for match in re.finditer(
            r"^FROM\s+\S+\s+AS\s+([a-z0-9-]+)\s*$",
            dockerfile,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    )
    assert stages == EXPECTED_DOCKER_STAGES

    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]
    assert "USER ${APP_UID}:${APP_GID}" in runtime
    assert "COPY --from=builder" in runtime
    assert "COPY --from=development" not in runtime
