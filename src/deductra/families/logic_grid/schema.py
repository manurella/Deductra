"""JSON Schema projection for the Logic Grid specification."""

from __future__ import annotations

import json
from typing import Any

from deductra.families.logic_grid.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridSpec,
)


def logic_grid_spec_json_schema() -> dict[str, Any]:
    """Return the versioned Logic Grid JSON Schema."""
    schema = LogicGridSpec.model_json_schema()
    identity = schema["$defs"]["PuzzleIdentity"]["properties"]
    identity["family_id"]["const"] = FAMILY_ID
    identity["schema_version"]["const"] = SPEC_SCHEMA_VERSION
    schema["$id"] = "urn:deductra:schema:logic-grid-spec:1"
    schema["title"] = "Deductra Logic Grid Specification v1"
    return schema


def rendered_logic_grid_spec_json_schema() -> str:
    """Return the normalized checked-in schema representation."""
    return (
        json.dumps(
            logic_grid_spec_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
