"""Enforce dependency boundaries for production Python imports."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "deductra"
ALLOWED_IMPORT_ROOTS = frozenset(sys.stdlib_module_names) | {"deductra", "pydantic"}
FORBIDDEN_INTERNAL_ROOTS = frozenset({"scripts", "tests"})


def imported_roots(path: Path) -> set[str]:
    """Return absolute top-level modules imported by one Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.partition(".")[0])
    return roots


def imported_modules(path: Path) -> set[str]:
    """Return absolute imported module names from one Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def production_sources() -> list[Path]:
    """Return production sources without generated caches."""
    return sorted(
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "__pycache__" not in path.relative_to(PACKAGE_ROOT).parts
    )


def test_production_imports_use_declared_roots() -> None:
    """Reject production imports outside the approved runtime dependency boundary."""
    violations: dict[str, list[str]] = {}
    for source in production_sources():
        undeclared = imported_roots(source) - ALLOWED_IMPORT_ROOTS
        if undeclared:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(undeclared)
    assert not violations, f"undeclared production imports: {violations}"


def test_production_does_not_depend_on_tests_or_repository_scripts() -> None:
    """Keep runtime code independent of validation and test infrastructure."""
    violations: dict[str, list[str]] = {}
    for source in production_sources():
        forbidden = imported_roots(source) & FORBIDDEN_INTERNAL_ROOTS
        if forbidden:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(forbidden)
    assert not violations, f"forbidden inward dependencies: {violations}"


def test_domain_package_does_not_import_outer_product_layers() -> None:
    """Keep the common domain independent of all later product capabilities."""
    violations: dict[str, list[str]] = {}
    for source in sorted((PACKAGE_ROOT / "domain").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith("deductra.domain")
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"domain imports outer product layers: {violations}"


def test_import_analysis_detects_an_undeclared_root(tmp_path: Path) -> None:
    """Prove that the import classifier sees an unapproved external root."""
    source = tmp_path / "module.py"
    source.write_text("import external_dependency\n", encoding="utf-8")
    assert imported_roots(source) == {"external_dependency"}
