"""JSON Schema projections for canonical reasoning contracts."""

from __future__ import annotations

import json
from typing import Any

from deductra.reasoning.events import EventEnvelope
from deductra.reasoning.state import PuzzleState


def event_envelope_json_schema() -> dict[str, Any]:
    """Return the versioned EventEnvelope JSON Schema."""
    schema = EventEnvelope.model_json_schema()
    schema["$id"] = "urn:deductra:schema:event-envelope:1"
    schema["title"] = "Deductra Event Envelope v1"
    return schema


def rendered_event_envelope_json_schema() -> str:
    """Return the normalized checked-in event schema representation."""
    return (
        json.dumps(
            event_envelope_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def puzzle_state_json_schema() -> dict[str, Any]:
    """Return the versioned PuzzleState JSON Schema."""
    schema = PuzzleState.model_json_schema()
    schema["$id"] = "urn:deductra:schema:puzzle-state:1"
    schema["title"] = "Deductra Puzzle State v1"
    return schema


def rendered_puzzle_state_json_schema() -> str:
    """Return the normalized checked-in state schema representation."""
    return (
        json.dumps(
            puzzle_state_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
