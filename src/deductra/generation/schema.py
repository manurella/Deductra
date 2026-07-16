"""JSON Schema projection for the generator-foundation contract."""

from __future__ import annotations

import json
from typing import Any

from deductra.generation.contracts import GenerationContractDocument


def generation_contract_json_schema() -> dict[str, Any]:
    """Return the versioned CR-007 generator-contract JSON Schema."""
    schema = GenerationContractDocument.model_json_schema()
    schema["$id"] = "urn:deductra:schema:generation-contract:1"
    schema["title"] = "Deductra Generation Contract v1"
    return schema


def rendered_generation_contract_json_schema() -> str:
    """Return the normalized checked-in generator-contract schema."""
    return (
        json.dumps(generation_contract_json_schema(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
