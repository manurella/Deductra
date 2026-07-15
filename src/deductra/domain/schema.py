"""JSON Schema projection for the common puzzle contract."""

from __future__ import annotations

import json
from typing import Any

from deductra.domain.puzzle import PuzzleSpec


def puzzle_spec_json_schema() -> dict[str, Any]:
    """Return the versioned PuzzleSpec JSON Schema as ordinary Python data."""
    schema = PuzzleSpec.model_json_schema()
    schema["$id"] = "urn:deductra:schema:puzzle-spec:1"
    schema["title"] = "Deductra Puzzle Specification v1"
    return schema


def rendered_puzzle_spec_json_schema() -> str:
    """Return the normalized checked-in schema representation."""
    return (
        json.dumps(
            puzzle_spec_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
