"""Typed specification boundary for the Logic Grid family."""

from deductra.families.logic_grid.schema import (
    logic_grid_spec_json_schema,
    rendered_logic_grid_spec_json_schema,
)
from deductra.families.logic_grid.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridCategory,
    LogicGridSpec,
)

__all__ = [
    "FAMILY_ID",
    "SPEC_SCHEMA_VERSION",
    "LogicGridCategory",
    "LogicGridSpec",
    "logic_grid_spec_json_schema",
    "rendered_logic_grid_spec_json_schema",
]
