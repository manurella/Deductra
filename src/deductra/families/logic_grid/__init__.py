"""Typed specification and reference boundary for the Logic Grid family."""

from deductra.families.logic_grid.checker import (
    LogicGridSolutionCheck,
    check_logic_grid_solution,
)
from deductra.families.logic_grid.golden import (
    GALLERY_OPENING_SOLUTION,
    HARBOR_MORNING_SOLUTION,
    OBSERVATORY_ROTATION_SOLUTION,
    gallery_opening,
    harbor_morning,
    logic_grid_goldens,
    observatory_rotation,
)
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
    "GALLERY_OPENING_SOLUTION",
    "HARBOR_MORNING_SOLUTION",
    "OBSERVATORY_ROTATION_SOLUTION",
    "SPEC_SCHEMA_VERSION",
    "LogicGridCategory",
    "LogicGridSolutionCheck",
    "LogicGridSpec",
    "check_logic_grid_solution",
    "discover_logic_grid_applications",
    "gallery_opening",
    "harbor_morning",
    "logic_grid_goldens",
    "logic_grid_rules",
    "logic_grid_spec_json_schema",
    "observatory_rotation",
    "rendered_logic_grid_spec_json_schema",
]
