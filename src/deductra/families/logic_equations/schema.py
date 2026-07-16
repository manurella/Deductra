"""JSON Schema projection for the Logic Equations specification."""

from __future__ import annotations

import json
from typing import Any

from deductra.families.logic_equations.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicEquationsSpec,
)


def logic_equations_spec_json_schema() -> dict[str, Any]:
    """Return the versioned Logic Equations JSON Schema."""
    schema = LogicEquationsSpec.model_json_schema()
    identity = schema["$defs"]["PuzzleIdentity"]["properties"]
    identity["family_id"]["const"] = FAMILY_ID
    identity["schema_version"]["const"] = SPEC_SCHEMA_VERSION
    schema["$id"] = "urn:deductra:schema:logic-equations-spec:1"
    schema["title"] = "Deductra Logic Equations Specification v1"
    return schema


def rendered_logic_equations_spec_json_schema() -> str:
    """Return the normalized checked-in schema representation."""
    return (
        json.dumps(
            logic_equations_spec_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
