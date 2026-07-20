"""JSON Schema projection for the Logic Grid specification."""

from __future__ import annotations

import json
from typing import Any

from deductra.families.logic_grid.builder import LogicGridBuilderDraft
from deductra.families.logic_grid.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridSpec,
)
from deductra.families.logic_grid.structured_io import (
    STRUCTURED_IO_SCHEMA_VERSION,
    LogicGridStructuredImport,
)


def logic_grid_builder_json_schema() -> dict[str, Any]:
    """Return the versioned guided-builder draft JSON Schema."""
    schema = LogicGridBuilderDraft.model_json_schema()
    schema["$id"] = "urn:deductra:schema:logic-grid-builder-draft:1"
    schema["title"] = "Deductra Logic Grid Builder Draft v1"
    schema["properties"]["schema_version"]["const"] = "1.0.0"
    return schema


def rendered_logic_grid_builder_json_schema() -> str:
    """Return the normalized checked-in guided-builder schema."""
    return (
        json.dumps(
            logic_grid_builder_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def logic_grid_structured_import_json_schema() -> dict[str, Any]:
    """Return the versioned structured-import result JSON Schema."""
    schema = LogicGridStructuredImport.model_json_schema()
    schema["$id"] = "urn:deductra:schema:logic-grid-structured-import:1"
    schema["title"] = "Deductra Logic Grid Structured Import Result v1"
    schema["properties"]["schema_version"]["const"] = STRUCTURED_IO_SCHEMA_VERSION
    return schema


def rendered_logic_grid_structured_import_json_schema() -> str:
    """Return the normalized checked-in structured-import result schema."""
    return (
        json.dumps(
            logic_grid_structured_import_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
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
