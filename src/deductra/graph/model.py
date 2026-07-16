"""Typed immutable contracts for the directed reasoning incidence hypergraph."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Self, cast

from pydantic import JsonValue, field_serializer, field_validator, model_validator

from deductra.domain.base import DomainModel, freeze_json, thaw_json
from deductra.domain.ids import GraphVertexId, HyperedgeId, PuzzleRevisionId
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.events import Sha256Digest


class VertexType(StrEnum):
    DOMAIN_OBJECT = "domain_object"
    ATOM = "atom"
    CONSTRAINT = "constraint"
    CLUE = "clue"
    STATE = "state"
    EVENT = "event"
    ASSUMPTION = "assumption"
    CONTRADICTION = "contradiction"
    SOLUTION = "solution"
    USER_ACTION = "user_action"
    AGENT_PROPOSAL = "agent_proposal"
    REPORT_SECTION = "report_section"


class HyperedgeType(StrEnum):
    CONSTRAINS = "constrains"
    DERIVES = "derives"
    ELIMINATES = "eliminates"
    ASSIGNS = "assigns"
    ASSUMES = "assumes"
    CONTRADICTS = "contradicts"
    RETRACTS = "retracts"
    VERIFIES = "verifies"
    GENERATES = "generates"
    USES_EVIDENCE = "uses_evidence"
    SUPERSEDES = "supersedes"
    PROJECTS_TO = "projects_to"
    EXPLAINS = "explains"
    RECOMMENDS = "recommends"


class GraphVertex(DomainModel):
    """One typed immutable vertex projected from a canonical source object."""

    vertex_id: GraphVertexId
    vertex_type: VertexType
    source_id: str
    content_hash: Sha256Digest
    attributes: Mapping[str, JsonValue]

    @field_validator("attributes", mode="after")
    @classmethod
    def freeze_attributes(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return cast(Mapping[str, JsonValue], freeze_json(value))

    @field_serializer("attributes")
    def serialize_attributes(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        return cast(dict[str, Any], thaw_json(value))


class DirectedHyperedge(DomainModel):
    """One directed many-to-many incidence relation."""

    edge_id: HyperedgeId
    edge_type: HyperedgeType
    source_id: str
    tail_vertex_ids: tuple[GraphVertexId, ...]
    head_vertex_ids: tuple[GraphVertexId, ...]
    sequence_no: int | None = None
    attributes: Mapping[str, JsonValue]

    @field_validator("tail_vertex_ids", "head_vertex_ids", mode="after")
    @classmethod
    def require_canonical_incidence(
        cls, value: tuple[GraphVertexId, ...]
    ) -> tuple[GraphVertexId, ...]:
        if not value:
            raise ValueError("hyperedge incidence sets cannot be empty")
        if value != tuple(sorted(set(value))):
            raise ValueError("hyperedge incidence identifiers must be unique and sorted")
        return value

    @field_validator("attributes", mode="after")
    @classmethod
    def freeze_attributes(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return cast(Mapping[str, JsonValue], freeze_json(value))

    @field_serializer("attributes")
    def serialize_attributes(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        return cast(dict[str, Any], thaw_json(value))


class ReasoningHypergraph(DomainModel):
    """Visual-neutral deterministic projection of canonical reasoning objects."""

    puzzle_revision_id: PuzzleRevisionId
    source_trace_hash: Sha256Digest
    vertices: tuple[GraphVertex, ...]
    edges: tuple[DirectedHyperedge, ...]
    graph_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        vertex_ids = tuple(item.vertex_id for item in self.vertices)
        edge_ids = tuple(item.edge_id for item in self.edges)
        if vertex_ids != tuple(sorted(set(vertex_ids))):
            raise ValueError("graph vertices must have unique sorted identifiers")
        if edge_ids != tuple(sorted(set(edge_ids))):
            raise ValueError("graph edges must have unique sorted identifiers")
        missing = evidence_closure_failures(self.vertices, self.edges)
        if missing:
            raise ValueError(f"hypergraph evidence closure failed: {missing}")
        if self.graph_hash != compute_hypergraph_hash(self):
            raise ValueError("graph_hash does not match canonical hypergraph contents")
        return self


def evidence_closure_failures(
    vertices: tuple[GraphVertex, ...], edges: tuple[DirectedHyperedge, ...]
) -> tuple[str, ...]:
    """Return every incidence reference that does not resolve to a vertex."""
    known = {item.vertex_id for item in vertices}
    return tuple(
        sorted(
            f"{edge.edge_id}:{vertex_id}"
            for edge in edges
            for vertex_id in (*edge.tail_vertex_ids, *edge.head_vertex_ids)
            if vertex_id not in known
        )
    )


def compute_hypergraph_hash(graph: ReasoningHypergraph) -> str:
    """Hash the complete graph except its self-digest."""
    return canonical_sha256(graph.model_dump(mode="json", exclude={"graph_hash"}))


def build_hypergraph(
    *,
    puzzle_revision_id: PuzzleRevisionId,
    source_trace_hash: str,
    vertices: tuple[GraphVertex, ...],
    edges: tuple[DirectedHyperedge, ...],
) -> ReasoningHypergraph:
    """Sort and seal a deterministic reasoning hypergraph."""
    ordered_vertices = tuple(sorted(vertices, key=lambda item: item.vertex_id))
    ordered_edges = tuple(sorted(edges, key=lambda item: item.edge_id))
    unsigned = ReasoningHypergraph.model_construct(
        puzzle_revision_id=puzzle_revision_id,
        source_trace_hash=source_trace_hash,
        vertices=ordered_vertices,
        edges=ordered_edges,
        graph_hash="0" * 64,
    )
    return ReasoningHypergraph(
        puzzle_revision_id=puzzle_revision_id,
        source_trace_hash=source_trace_hash,
        vertices=ordered_vertices,
        edges=ordered_edges,
        graph_hash=compute_hypergraph_hash(unsigned),
    )
