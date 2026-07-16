"""Typed directed hypergraph projection and visual-neutral export."""

from deductra.graph.export import canonical_hypergraph_json
from deductra.graph.model import (
    DirectedHyperedge,
    GraphVertex,
    HyperedgeType,
    ReasoningHypergraph,
    VertexType,
    compute_hypergraph_hash,
    evidence_closure_failures,
)
from deductra.graph.projector import HypergraphProjectionError, project_reasoning_hypergraph

__all__ = [
    "DirectedHyperedge",
    "GraphVertex",
    "HyperedgeType",
    "HypergraphProjectionError",
    "ReasoningHypergraph",
    "VertexType",
    "canonical_hypergraph_json",
    "compute_hypergraph_hash",
    "evidence_closure_failures",
    "project_reasoning_hypergraph",
]
