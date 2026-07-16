"""Typed specification boundary for the Logic Equations family."""

from deductra.families.logic_equations.schema import (
    logic_equations_spec_json_schema,
    rendered_logic_equations_spec_json_schema,
)
from deductra.families.logic_equations.solver import (
    discover_logic_equations_applications,
    logic_equations_rules,
)
from deductra.families.logic_equations.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicEquationsSpec,
)

__all__ = [
    "FAMILY_ID",
    "SPEC_SCHEMA_VERSION",
    "LogicEquationsSpec",
    "discover_logic_equations_applications",
    "logic_equations_rules",
    "logic_equations_spec_json_schema",
    "rendered_logic_equations_spec_json_schema",
]
