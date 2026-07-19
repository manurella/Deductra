"""Typed specification boundary for the Logic Grid family."""

from deductra.families.logic_grid.schema import (
    logic_grid_spec_json_schema,
    rendered_logic_grid_spec_json_schema,
)
from deductra.families.logic_grid.solver import (
    discover_logic_grid_applications,
    logic_grid_rules,
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
    "discover_logic_grid_applications",
    "logic_grid_rules",
    "logic_grid_spec_json_schema",
    "rendered_logic_grid_spec_json_schema",
]
