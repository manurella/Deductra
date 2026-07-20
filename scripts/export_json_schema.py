"""Export the canonical PuzzleSpec JSON Schema deterministically."""

from __future__ import annotations

from pathlib import Path

from deductra.agents.schema import rendered_agent_boundary_json_schema
from deductra.domain.schema import rendered_puzzle_spec_json_schema
from deductra.families.logic_equations.schema import (
    rendered_logic_equations_spec_json_schema,
)
from deductra.families.logic_grid.schema import (
    rendered_logic_grid_attempt_record_json_schema,
    rendered_logic_grid_builder_json_schema,
    rendered_logic_grid_play_session_json_schema,
    rendered_logic_grid_spec_json_schema,
    rendered_logic_grid_structured_import_json_schema,
)
from deductra.generation.schema import rendered_generation_contract_json_schema
from deductra.graph.schema import rendered_reasoning_hypergraph_json_schema
from deductra.memory.projections.schema import rendered_memory_projection_json_schema
from deductra.reasoning.schema import (
    rendered_event_envelope_json_schema,
    rendered_human_solve_trace_json_schema,
    rendered_puzzle_state_json_schema,
)
from deductra.reports.schema import rendered_report_model_json_schema
from deductra.verification.schema import rendered_verification_record_json_schema

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "puzzle-spec-v1.schema.json"
EVENT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "event-envelope-v1.schema.json"
STATE_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "puzzle-state-v1.schema.json"
HUMAN_TRACE_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "human-solve-trace-v1.schema.json"
HYPERGRAPH_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "reasoning-hypergraph-v1.schema.json"
GENERATION_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "generation-contract-v1.schema.json"
MEMORY_PROJECTION_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "memory-projections-v1.schema.json"
VERIFICATION_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "verification-record-v1.schema.json"
REPORT_MODEL_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "report-model-v1.schema.json"
AGENT_BOUNDARY_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "agent-boundary-v1.schema.json"
LOGIC_EQUATIONS_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "logic-equations-spec-v1.schema.json"
LOGIC_GRID_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "logic-grid-spec-v1.schema.json"
LOGIC_GRID_BUILDER_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "logic-grid-builder-draft-v1.schema.json"
)
LOGIC_GRID_STRUCTURED_IMPORT_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "logic-grid-structured-import-v1.schema.json"
)
LOGIC_GRID_PLAY_SESSION_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "logic-grid-play-session-v1.schema.json"
)
LOGIC_GRID_ATTEMPT_RECORD_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "logic-grid-attempt-record-v1.schema.json"
)


def main() -> None:
    """Write the generated schema to its canonical public path."""
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(
        rendered_puzzle_spec_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    EVENT_SCHEMA_PATH.write_text(
        rendered_event_envelope_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    STATE_SCHEMA_PATH.write_text(
        rendered_puzzle_state_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    HUMAN_TRACE_SCHEMA_PATH.write_text(
        rendered_human_solve_trace_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    HYPERGRAPH_SCHEMA_PATH.write_text(
        rendered_reasoning_hypergraph_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    GENERATION_SCHEMA_PATH.write_text(
        rendered_generation_contract_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    MEMORY_PROJECTION_SCHEMA_PATH.write_text(
        rendered_memory_projection_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    VERIFICATION_SCHEMA_PATH.write_text(
        rendered_verification_record_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    REPORT_MODEL_SCHEMA_PATH.write_text(
        rendered_report_model_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    AGENT_BOUNDARY_SCHEMA_PATH.write_text(
        rendered_agent_boundary_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    LOGIC_EQUATIONS_SCHEMA_PATH.write_text(
        rendered_logic_equations_spec_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    LOGIC_GRID_SCHEMA_PATH.write_text(
        rendered_logic_grid_spec_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    LOGIC_GRID_BUILDER_SCHEMA_PATH.write_text(
        rendered_logic_grid_builder_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    LOGIC_GRID_STRUCTURED_IMPORT_SCHEMA_PATH.write_text(
        rendered_logic_grid_structured_import_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    LOGIC_GRID_PLAY_SESSION_SCHEMA_PATH.write_text(
        rendered_logic_grid_play_session_json_schema(),
        encoding="utf-8",
        newline="\n",
    )
    LOGIC_GRID_ATTEMPT_RECORD_SCHEMA_PATH.write_text(
        rendered_logic_grid_attempt_record_json_schema(),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
