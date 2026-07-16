"""End-to-end acceptance tests for the FAM-LE-005 command line."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

from deductra.cli import main, render_trace, solve_four_sigils
from deductra.reasoning import HumanSolveStatus, HumanSolveTrace


def test_solve_prints_the_verified_golden_solution() -> None:
    output = io.StringIO()
    error = io.StringIO()
    result = main(("solve", "four-sigils"), output=output, error=error)

    assert result == 0
    assert error.getvalue() == ""
    assert output.getvalue().splitlines()[:5] == [
        "The Four Sigils: solved",
        "Ember = 1",
        "Tide = 2",
        "Gale = 3",
        "Stone = 4",
    ]
    assert "Trace hash: " in output.getvalue()


def test_trace_export_is_canonical_and_round_trips(tmp_path: Path) -> None:
    first_path = tmp_path / "first-trace.json"
    second_path = tmp_path / "second-trace.json"

    assert main(("solve", "four-sigils", "--trace", str(first_path))) == 0
    assert main(("solve", "four-sigils", "--trace", str(second_path))) == 0

    first = first_path.read_text(encoding="utf-8")
    assert first == second_path.read_text(encoding="utf-8")
    restored = HumanSolveTrace.model_validate_json(first)
    assert restored.status is HumanSolveStatus.SOLVED
    assert first == render_trace(restored)


def test_trace_export_refuses_to_overwrite(tmp_path: Path) -> None:
    trace_path = tmp_path / "existing.json"
    trace_path.write_text("owner content\n", encoding="utf-8")
    output = io.StringIO()
    error = io.StringIO()

    result = main(
        ("solve", "four-sigils", "--trace", str(trace_path)),
        output=output,
        error=error,
    )

    assert result == 1
    assert output.getvalue() == ""
    assert "trace path already exists" in error.getvalue()
    assert trace_path.read_text(encoding="utf-8") == "owner content\n"


def test_module_entry_point_executes_the_same_solve() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "deductra", "solve", "four-sigils"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert "The Four Sigils: solved" in result.stdout


def test_canonical_solve_is_stable_across_calls() -> None:
    assert solve_four_sigils() == solve_four_sigils()
