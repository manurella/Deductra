"""JSON Schema projection for the reasoning hypergraph contract."""

from __future__ import annotations

import json
from typing import Any

from deductra.graph.model import ReasoningHypergraph


def reasoning_hypergraph_json_schema() -> dict[str, Any]:
    schema = ReasoningHypergraph.model_json_schema()
    schema["$id"] = "urn:deductra:schema:reasoning-hypergraph:1"
    schema["title"] = "Deductra Reasoning Hypergraph v1"
    return schema


def rendered_reasoning_hypergraph_json_schema() -> str:
    return (
        json.dumps(reasoning_hypergraph_json_schema(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
