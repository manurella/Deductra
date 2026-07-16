"""Export the canonical PuzzleSpec JSON Schema deterministically."""

from __future__ import annotations

from pathlib import Path

from deductra.domain.schema import rendered_puzzle_spec_json_schema
from deductra.reasoning.schema import (
    rendered_event_envelope_json_schema,
    rendered_puzzle_state_json_schema,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "puzzle-spec-v1.schema.json"
EVENT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "event-envelope-v1.schema.json"
STATE_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "puzzle-state-v1.schema.json"


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


if __name__ == "__main__":
    main()
