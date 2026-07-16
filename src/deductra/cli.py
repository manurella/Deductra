"""Narrow command-line delivery adapter for the Logic Equations kernel."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from deductra import __version__
from deductra.families.logic_equations import (
    FOUR_SIGILS_SOLUTION,
    check_logic_equations_solution,
    four_sigils,
    logic_equations_rules,
)
from deductra.reasoning import (
    GENESIS_EVENT_HASH,
    HumanReasoningEngine,
    HumanSolveContext,
    HumanSolveStatus,
    HumanSolveTrace,
    ProducerRef,
    create_initial_state,
)
from deductra.verification import (
    CpSatProofBackend,
    CrossVerificationCoordinator,
    VerifiedRuleAuthority,
    Z3ProofBackend,
)


class CliExecutionError(RuntimeError):
    """A user-facing CLI failure that does not require a traceback."""


def solve_four_sigils() -> HumanSolveTrace:
    """Run the canonical, cross-verified Golden Easy solve."""
    puzzle = four_sigils()
    solution_check = check_logic_equations_solution(puzzle, FOUR_SIGILS_SOLUTION)
    if not solution_check.accepted:
        raise CliExecutionError("the canonical solution failed its family checker")

    initial_state = create_initial_state(
        puzzle,
        state_id="deductra:state:four-sigils:cli:initial",
        branch_id="deductra:branch:four-sigils:cli",
        sequence_no=0,
    )
    authority = VerifiedRuleAuthority(
        CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
    )
    trace = HumanReasoningEngine(logic_equations_rules(), authority).solve(
        puzzle,
        initial_state,
        HumanSolveContext(
            trace_id="deductra:trace:four-sigils:cli",
            correlation_id="deductra:correlation:four-sigils:cli",
            producer=ProducerRef(
                producer_id="deductra:producer:logic-equations-cli",
                kind="tool",
                version="1.0.0",
            ),
            occurred_at=puzzle.identity.created_at,
            previous_event_hash=GENESIS_EVENT_HASH,
        ),
    )
    if trace.status is not HumanSolveStatus.SOLVED:
        raise CliExecutionError(f"the canonical human solve ended with status {trace.status.value}")
    return trace


def render_trace(trace: HumanSolveTrace) -> str:
    """Render a stable, human-readable representation of the canonical trace."""
    return (
        json.dumps(
            trace.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_trace(path: Path, trace: HumanSolveTrace) -> None:
    """Create one trace file without overwriting an existing artifact."""
    try:
        with path.open("x", encoding="utf-8", newline="\n") as trace_file:
            trace_file.write(render_trace(trace))
    except FileExistsError as error:
        raise CliExecutionError(f"trace path already exists: {path}") from error
    except OSError as error:
        raise CliExecutionError(f"could not write trace path {path}: {error}") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deductra",
        description="Solve verified Deductra reference puzzles.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    solve = commands.add_parser(
        "solve",
        help="solve a supported reference puzzle",
    )
    solve.add_argument(
        "puzzle",
        choices=("four-sigils",),
        help="reference puzzle identifier",
    )
    solve.add_argument(
        "--trace",
        type=Path,
        help="create a canonical JSON solve trace at this path",
    )
    return parser


def _print_solution(trace: HumanSolveTrace, output: TextIO) -> None:
    puzzle = four_sigils()
    labels = {variable.variable_id: variable.label for variable in puzzle.variables}
    values = {value.value_id: value.label for domain in puzzle.domains for value in domain.values}
    print(f"{puzzle.identity.title}: solved", file=output)
    for assignment in FOUR_SIGILS_SOLUTION:
        print(
            f"{labels[assignment.variable_id]} = {values[assignment.value_id]}",
            file=output,
        )
    print(f"Trace hash: {trace.trace_hash}", file=output)


def main(
    argv: Sequence[str] | None = None,
    *,
    output: TextIO | None = None,
    error: TextIO | None = None,
) -> int:
    """Run the CLI and return a process-compatible exit status."""
    arguments = _parser().parse_args(argv)
    stdout = output if output is not None else sys.stdout
    stderr = error if error is not None else sys.stderr

    try:
        if arguments.command != "solve" or arguments.puzzle != "four-sigils":
            raise CliExecutionError("unsupported command")
        trace = solve_four_sigils()
        trace_path: Path | None = arguments.trace
        if trace_path is not None:
            write_trace(trace_path, trace)
        _print_solution(trace, stdout)
        if trace_path is not None:
            print(f"Trace written to: {trace_path}", file=stdout)
    except CliExecutionError as failure:
        print(f"deductra: error: {failure}", file=stderr)
        return 1
    return 0
