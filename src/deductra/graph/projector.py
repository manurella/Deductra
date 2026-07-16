"""Deterministic projection from puzzle and verified human trace to a hypergraph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel, JsonValue

from deductra.domain.atoms import Atom
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_sha256
from deductra.graph.model import (
    DirectedHyperedge,
    GraphVertex,
    HyperedgeType,
    ReasoningHypergraph,
    VertexType,
    build_hypergraph,
)
from deductra.reasoning.engine import DeductionAuthorityStatus, HumanSolveTrace
from deductra.reasoning.events import CandidatesEliminated, ValueAssigned


class HypergraphProjectionError(ValueError):
    """Canonical sources cannot be projected without losing evidence."""


def _vertex(
    vertex_type: VertexType,
    source_id: str,
    content: object,
    *,
    source_kind: str,
) -> GraphVertex:
    identity = canonical_sha256({"source_id": source_id, "vertex_type": vertex_type})
    return GraphVertex(
        vertex_id=f"deductra:vertex:{identity}",
        vertex_type=vertex_type,
        source_id=source_id,
        content_hash=canonical_sha256(content),
        attributes={"source_kind": source_kind},
    )


def _edge(
    edge_type: HyperedgeType,
    source_id: str,
    tail: set[str],
    head: set[str],
    *,
    sequence_no: int | None = None,
    attributes: Mapping[str, JsonValue] | None = None,
) -> DirectedHyperedge:
    identity = canonical_sha256(
        {
            "edge_type": edge_type,
            "head": sorted(head),
            "source_id": source_id,
            "tail": sorted(tail),
        }
    )
    return DirectedHyperedge(
        edge_id=f"deductra:edge:{identity}",
        edge_type=edge_type,
        source_id=source_id,
        tail_vertex_ids=tuple(sorted(tail)),
        head_vertex_ids=tuple(sorted(head)),
        sequence_no=sequence_no,
        attributes=attributes or {},
    )


def _variable_references(value: object) -> set[str]:
    if isinstance(value, BaseModel):
        return _variable_references(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        found: set[str] = set()
        for key, item in mapping.items():
            if key.endswith("variable_id") and isinstance(item, str):
                found.add(item)
            elif key.endswith("variable_ids") and isinstance(item, list):
                found.update(cast(list[str], item))
            else:
                found.update(_variable_references(item))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in cast(list[object], value):
            found.update(_variable_references(item))
        return found
    return set()


def project_reasoning_hypergraph(
    puzzle: PuzzleSpec,
    trace: HumanSolveTrace,
) -> ReasoningHypergraph:
    """Rebuild a closed visual-neutral hypergraph from immutable canonical inputs."""
    if trace.puzzle_revision_id != puzzle.identity.revision_id:
        raise HypergraphProjectionError("trace and puzzle revisions do not match")

    vertices: dict[str, GraphVertex] = {}
    source_vertices: dict[tuple[VertexType, str], str] = {}
    edges: list[DirectedHyperedge] = []

    def add(vertex: GraphVertex) -> str:
        existing = vertices.get(vertex.vertex_id)
        if existing is not None and existing != vertex:
            raise HypergraphProjectionError("stable vertex identity has conflicting contents")
        vertices[vertex.vertex_id] = vertex
        source_vertices[(vertex.vertex_type, vertex.source_id)] = vertex.vertex_id
        return vertex.vertex_id

    puzzle_vertex = add(
        _vertex(
            VertexType.DOMAIN_OBJECT,
            puzzle.identity.revision_id,
            puzzle.identity,
            source_kind="puzzle_revision",
        )
    )
    variable_vertices: dict[str, str] = {}
    constraint_vertices: dict[str, str] = {}
    for domain in puzzle.domains:
        domain_vertex = add(
            _vertex(VertexType.DOMAIN_OBJECT, domain.domain_id, domain, source_kind="domain")
        )
        value_vertices = {
            add(
                _vertex(
                    VertexType.DOMAIN_OBJECT,
                    value.value_id,
                    value,
                    source_kind="domain_value",
                )
            )
            for value in domain.values
        }
        edges.append(
            _edge(HyperedgeType.PROJECTS_TO, domain.domain_id, {domain_vertex}, value_vertices)
        )
    for variable in puzzle.variables:
        variable_vertices[variable.variable_id] = add(
            _vertex(
                VertexType.DOMAIN_OBJECT,
                variable.variable_id,
                variable,
                source_kind="variable",
            )
        )
    for constraint in puzzle.constraints:
        constraint_vertex = add(
            _vertex(
                VertexType.CONSTRAINT,
                constraint.constraint_id,
                constraint,
                source_kind="constraint",
            )
        )
        constraint_vertices[constraint.constraint_id] = constraint_vertex
        referenced = {
            variable_vertices[item]
            for item in _variable_references(constraint)
            if item in variable_vertices
        }
        edges.append(
            _edge(
                HyperedgeType.CONSTRAINS,
                constraint.constraint_id,
                referenced or {puzzle_vertex},
                {constraint_vertex},
            )
        )
    for clue in puzzle.clues:
        clue_vertex = add(_vertex(VertexType.CLUE, clue.clue_id, clue, source_kind="clue"))
        tail = {
            constraint_vertices[item] for item in clue.constraint_ids if item in constraint_vertices
        }
        edges.append(
            _edge(HyperedgeType.EXPLAINS, clue.clue_id, tail or {puzzle_vertex}, {clue_vertex})
        )

    state_hashes = {trace.initial_state_hash, trace.final_state_hash}
    for attempt in trace.attempts:
        state_hashes.add(attempt.source_state_hash)
        if attempt.result_state_hash is not None:
            state_hashes.add(attempt.result_state_hash)
    state_vertices = {
        item: add(_vertex(VertexType.STATE, item, {"state_hash": item}, source_kind="state"))
        for item in state_hashes
    }
    event_vertices = {
        event.event_id: add(
            _vertex(VertexType.EVENT, event.event_id, event, source_kind="reasoning_event")
        )
        for event in trace.events
    }

    def atom_vertex(atom: Atom) -> str:
        source_id = f"atom:{canonical_sha256(atom)}"
        return add(_vertex(VertexType.ATOM, source_id, atom, source_kind="atom"))

    for attempt in trace.attempts:
        if attempt.verification_status not in {
            DeductionAuthorityStatus.BACKEND_VERIFIED,
            DeductionAuthorityStatus.CROSS_VERIFIED,
        }:
            continue
        if (
            attempt.event_id is None
            or attempt.result_state_hash is None
            or len(attempt.conclusions) != 1
        ):
            raise HypergraphProjectionError("verified attempt has incomplete evidence")
        event = next((item for item in trace.events if item.event_id == attempt.event_id), None)
        if event is None:
            raise HypergraphProjectionError("verified attempt event is absent from the trace")
        rule_vertex = add(
            _vertex(
                VertexType.DOMAIN_OBJECT,
                attempt.rule.rule_id,
                attempt.rule,
                source_kind="reasoning_rule",
            )
        )
        certificate_vertices = {
            add(
                _vertex(
                    VertexType.DOMAIN_OBJECT,
                    certificate_id,
                    {"certificate_id": certificate_id},
                    source_kind="verification_certificate",
                )
            )
            for certificate_id in attempt.certificate_ids
        }
        tail = {
            state_vertices[attempt.source_state_hash],
            rule_vertex,
            *certificate_vertices,
            *(atom_vertex(item) for item in attempt.premises),
            *(constraint_vertices[item] for item in attempt.supporting_constraints),
        }
        head = {
            state_vertices[attempt.result_state_hash],
            event_vertices[attempt.event_id],
            atom_vertex(attempt.conclusions[0]),
        }
        if isinstance(event.payload, ValueAssigned):
            edge_type = HyperedgeType.ASSIGNS
        elif isinstance(event.payload, CandidatesEliminated):
            edge_type = HyperedgeType.ELIMINATES
        else:
            raise HypergraphProjectionError("verified deduction event has unsupported semantics")
        edges.append(
            _edge(
                edge_type,
                attempt.event_id,
                tail,
                head,
                sequence_no=event.sequence_no,
                attributes={
                    "candidate_id": attempt.candidate_id,
                    "obligation_id": attempt.obligation_id,
                    "verification_status": attempt.verification_status,
                },
            )
        )

    return build_hypergraph(
        puzzle_revision_id=puzzle.identity.revision_id,
        source_trace_hash=trace.trace_hash,
        vertices=tuple(vertices.values()),
        edges=tuple(edges),
    )
