"""JSON Schema projection for rebuildable memory views."""

from __future__ import annotations

import json
from typing import Any

from deductra.memory.projections.model import MemoryProjectionContractDocument


def memory_projection_json_schema() -> dict[str, Any]:
    schema = MemoryProjectionContractDocument.model_json_schema()
    schema["$id"] = "urn:deductra:schema:memory-projections:1"
    schema["title"] = "Deductra Memory Projections v1"
    return schema


def rendered_memory_projection_json_schema() -> str:
    return (
        json.dumps(memory_projection_json_schema(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
