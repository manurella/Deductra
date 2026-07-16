from __future__ import annotations

from pathlib import Path

from deductra.agents.schema import rendered_agent_boundary_json_schema

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_agent_boundary_schema_matches_contract() -> None:
    schema_path = REPOSITORY_ROOT / "schemas" / "agent-boundary-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == rendered_agent_boundary_json_schema()
