"""Enforce dependency boundaries for production Python imports."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "deductra"
ALLOWED_IMPORT_ROOTS = frozenset(sys.stdlib_module_names) | {
    "deductra",
    "google",
    "jinja2",
    "ortools",
    "pydantic",
    "weasyprint",
    "yaml",
    "z3",
}
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


def dynamically_imported_modules(path: Path) -> set[str]:
    """Return literal module names passed to import_module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "import_module"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            modules.add(node.args[0].value)
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


def test_reasoning_package_does_not_import_persistence_or_outer_layers() -> None:
    """Allow reasoning to depend on domain contracts but never persistence details."""
    violations: dict[str, list[str]] = {}
    allowed = ("deductra.domain", "deductra.reasoning")
    for source in sorted((PACKAGE_ROOT / "reasoning").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"reasoning imports persistence or outer layers: {violations}"


def test_memory_package_depends_only_on_inward_contracts() -> None:
    """Keep persistence adapters dependent on domain and reasoning, never delivery layers."""
    violations: dict[str, list[str]] = {}
    allowed = ("deductra.domain", "deductra.reasoning", "deductra.memory")
    for source in sorted((PACKAGE_ROOT / "memory").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"memory imports outer layers: {violations}"


def test_memory_projection_package_depends_only_on_approved_sources() -> None:
    """Allow derived views to consume generation contracts without solver authority."""
    violations: dict[str, list[str]] = {}
    allowed = (
        "deductra.domain",
        "deductra.reasoning",
        "deductra.generation",
        "deductra.memory",
    )
    for source in sorted((PACKAGE_ROOT / "memory" / "projections").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"memory projections import authoritative outer layers: {violations}"


def test_verification_package_depends_only_on_inward_contracts() -> None:
    """Keep proof backends dependent on domain and reasoning contracts only."""
    violations: dict[str, list[str]] = {}
    allowed = ("deductra.domain", "deductra.reasoning", "deductra.verification")
    for source in sorted((PACKAGE_ROOT / "verification").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"verification imports outer layers: {violations}"


def test_graph_package_depends_only_on_canonical_inward_contracts() -> None:
    """Keep graph projection read-only over domain and reasoning contracts."""
    violations: dict[str, list[str]] = {}
    allowed = ("deductra.domain", "deductra.reasoning", "deductra.graph")
    for source in sorted((PACKAGE_ROOT / "graph").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"graph imports non-canonical outer layers: {violations}"


def test_generation_package_depends_only_on_evidence_contracts() -> None:
    """Keep generator contracts independent of persistence, solvers, UI, and reports."""
    violations: dict[str, list[str]] = {}
    allowed = ("deductra.domain", "deductra.reasoning", "deductra.generation")
    for source in sorted((PACKAGE_ROOT / "generation").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"generation imports authoritative outer layers: {violations}"


def test_family_specifications_depend_only_on_common_domain_contracts() -> None:
    """Keep concrete family data contracts independent of outer capabilities."""
    violations: dict[str, list[str]] = {}
    allowed = ("deductra.domain", "deductra.families")
    family_roots = tuple(
        PACKAGE_ROOT / "families" / family_name for family_name in ("logic_equations", "logic_grid")
    )
    for source in (
        family_root / filename
        for family_root in family_roots
        for filename in ("specification.py", "schema.py")
    ):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"family specifications import outer capabilities: {violations}"


def test_family_rules_depend_only_on_domain_and_reasoning_contracts() -> None:
    """Keep family reasoning independent of authority and outer integrations."""
    violations: dict[str, list[str]] = {}
    allowed = ("deductra.domain", "deductra.families", "deductra.reasoning")
    family_roots = tuple(
        PACKAGE_ROOT / "families" / family_name for family_name in ("logic_equations", "logic_grid")
    )
    for source in (
        family_root / filename
        for family_root in family_roots
        for filename in ("rules.py", "solver.py")
    ):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"family rules import authoritative outer layers: {violations}"


def test_family_builders_are_bounded_outer_application_services() -> None:
    """Allow family authoring to compose proof without importing unrelated outer layers."""
    violations: dict[str, list[str]] = {}
    allowed = (
        "deductra.domain",
        "deductra.families",
        "deductra.reasoning",
        "deductra.verification",
    )
    for source in (
        PACKAGE_ROOT / "families" / "logic_grid" / "builder.py",
        PACKAGE_ROOT / "families" / "logic_grid" / "structured_io.py",
    ):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"family builders import unrelated outer layers: {violations}"


def test_cli_is_an_outer_delivery_adapter() -> None:
    """Allow CLI composition without permitting delivery dependencies to point inward."""
    allowed = (
        "deductra.cli",
        "deductra.domain",
        "deductra.families",
        "deductra.reasoning",
        "deductra.verification",
    )
    violations: dict[str, list[str]] = {}
    for source in (PACKAGE_ROOT / "__main__.py", PACKAGE_ROOT / "cli.py"):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"CLI imports unapproved capabilities: {violations}"


def test_reports_are_downstream_of_authoritative_contracts() -> None:
    """Keep reports derived from canonical contracts and independent of adapters."""
    violations: dict[str, list[str]] = {}
    allowed = (
        "deductra.domain",
        "deductra.reasoning",
        "deductra.verification",
        "deductra.reports",
    )
    for source in sorted((PACKAGE_ROOT / "reports").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"reports import non-canonical outer layers: {violations}"


def test_agents_are_an_optional_outer_integration_boundary() -> None:
    """Allow agents to read deterministic contracts without inward authority."""
    violations: dict[str, list[str]] = {}
    allowed = (
        "deductra.domain",
        "deductra.reasoning",
        "deductra.verification",
        "deductra.agents",
    )
    for source in sorted((PACKAGE_ROOT / "agents").glob("*.py")):
        outward = {
            module
            for module in imported_modules(source)
            if module.startswith("deductra.") and not module.startswith(allowed)
        }
        if outward:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(outward)
    assert not violations, f"agents import non-canonical outer layers: {violations}"


def test_provider_sdk_imports_are_confined_to_agent_adapter() -> None:
    """Prevent provider SDK coupling outside the reviewed integration module."""
    allowed_path = PACKAGE_ROOT / "agents" / "openai_runtime.py"
    violations: dict[str, list[str]] = {}
    for source in production_sources():
        provider_imports = (
            imported_roots(source)
            | {module.partition(".")[0] for module in dynamically_imported_modules(source)}
        ) & {"agents", "openai"}
        if provider_imports and source != allowed_path:
            violations[source.relative_to(REPOSITORY_ROOT).as_posix()] = sorted(provider_imports)
    assert not violations, f"provider SDK imports outside agent adapter: {violations}"


def test_import_analysis_detects_an_undeclared_root(tmp_path: Path) -> None:
    """Prove that the import classifier sees an unapproved external root."""
    source = tmp_path / "module.py"
    source.write_text("import external_dependency\n", encoding="utf-8")
    assert imported_roots(source) == {"external_dependency"}
