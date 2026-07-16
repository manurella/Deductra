"""Canonical visual-neutral JSON export for reasoning hypergraphs."""

from deductra.domain.serialization import canonical_json
from deductra.graph.model import ReasoningHypergraph


def canonical_hypergraph_json(graph: ReasoningHypergraph) -> str:
    """Return stable renderer-independent JSON with a trailing newline."""
    return canonical_json(graph) + "\n"
