"""CR-006 acceptance tests for deterministic closed hypergraph projection."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from deductra.domain.atoms import AssignmentAtom, Atom
from deductra.domain.constraints import AllDifferentConstraint
from deductra.domain.puzzle import DisplaySpec, ProvenanceBundle, PuzzleIdentity, PuzzleSpec
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.graph import (
    HyperedgeType,
    HypergraphProjectionError,
    canonical_hypergraph_json,
    evidence_closure_failures,
    project_reasoning_hypergraph,
)
from deductra.graph.schema import rendered_reasoning_hypergraph_json_schema
from deductra.reasoning import (
    DeductionAuthorityStatus,
    HumanReasoningAttempt,
    HumanSolveStatus,
    HumanSolveTrace,
    ProducerRef,
    ReasoningPolicy,
    RuleReference,
    ValueAssigned,
    compute_human_trace_hash,
    reduce_state,
    seal_event,
)
from deductra.reasoning.state import build_state

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]
X = "deductra:variable:x"
Y = "deductra:variable:y"
A = "deductra:value:a"
B = "deductra:value:b"


def puzzle() -> PuzzleSpec:
    values = (DomainValue(value_id=A, label="A"), DomainValue(value_id=B, label="B"))
    return PuzzleSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:graph-test",
            revision_id="deductra:revision:graph-test:1",
            family_id="graph-test",
            schema_version="1.0.0",
            title="Graph test",
            source_kind="golden",
            created_at=NOW,
        ),
        domains=(
            Domain(
                domain_id="deductra:domain:letters",
                values=values,
                ordered=False,
                distinct_by_default=True,
            ),
        ),
        variables=tuple(
            Variable(
                variable_id=item,
                label=item.rsplit(":", 1)[1].upper(),
                domain_id="deductra:domain:letters",
                role="answer",
            )
            for item in (X, Y)
        ),
        constraints=(
            AllDifferentConstraint(
                constraint_id="deductra:constraint:different",
                label="Values differ",
                variable_ids=(X, Y),
            ),
        ),
        clues=(),
        givens=(),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def sources() -> tuple[PuzzleSpec, HumanSolveTrace]:
    spec = puzzle()
    premise = AssignmentAtom(variable_id=Y, value_id=A)
    conclusion = AssignmentAtom(variable_id=X, value_id=B)
    state = build_state(
        state_id="deductra:state:graph-source",
        puzzle_revision_id=spec.identity.revision_id,
        sequence_no=1,
        branch_id="deductra:branch:root",
        candidate_domains={X: frozenset({A, B}), Y: frozenset({A})},
        asserted_atoms=cast(frozenset[Atom], frozenset({cast(Any, premise)})),
        rejected_atoms=frozenset(),
        active_constraint_ids=frozenset({"deductra:constraint:different"}),
        contradiction_ids=(),
    )
    event = seal_event(
        event_id="deductra:event:graph-assignment",
        trace_id="deductra:trace:graph-test",
        puzzle_revision_id=spec.identity.revision_id,
        branch_id=state.branch_id,
        sequence_no=2,
        schema_version="1.0.0",
        occurred_at=NOW,
        producer=ProducerRef(
            producer_id="deductra:producer:graph-test",
            kind="rule_engine",
            version="1.0.0",
        ),
        correlation_id="deductra:correlation:graph-test",
        previous_event_hash="a" * 64,
        payload=ValueAssigned(
            variable_id=X,
            value_id=B,
            source_state_hash=state.state_hash,
            result_state_id="deductra:state:graph-result",
            origin="human_rule",
        ),
    )
    result = reduce_state(state, event)
    attempt = HumanReasoningAttempt(
        candidate_id="deductra:candidate:graph-assignment",
        source_state_hash=state.state_hash,
        rule=RuleReference(
            rule_id="deductra:rule:graph-assignment",
            rule_version="1.0.0",
            family_scope=("graph-test",),
            title="Assign remaining value",
            technique_rank=1,
        ),
        premises=(premise,),
        conclusions=(conclusion,),
        supporting_constraints=("deductra:constraint:different",),
        proposal_hash="b" * 64,
        obligation_id="deductra:obligation:graph-assignment",
        verification_status=DeductionAuthorityStatus.CROSS_VERIFIED,
        certificate_ids=("deductra:certificate:one", "deductra:certificate:two"),
        reason="the negated claim is unsatisfiable",
        event_id=event.event_id,
        result_state_hash=result.state_hash,
    )
    unsigned = HumanSolveTrace.model_construct(
        trace_id=event.trace_id,
        puzzle_revision_id=spec.identity.revision_id,
        policy=ReasoningPolicy.FAMILY_CANONICAL,
        status=HumanSolveStatus.SOLVED,
        stalled_reason=None,
        initial_state_hash=state.state_hash,
        final_state_hash=result.state_hash,
        attempts=(attempt,),
        events=(event,),
        trace_hash="0" * 64,
    )
    trace = HumanSolveTrace(
        **unsigned.model_dump(exclude={"trace_hash"}),
        trace_hash=compute_human_trace_hash(unsigned),
    )
    return spec, trace


def test_projection_is_byte_deterministic_and_visual_neutral() -> None:
    spec, trace = sources()
    first = project_reasoning_hypergraph(spec, trace)
    second = project_reasoning_hypergraph(spec, trace)
    assert first == second
    assert canonical_hypergraph_json(first) == canonical_hypergraph_json(second)
    exported = json.loads(canonical_hypergraph_json(first))
    assert exported["graph_hash"] == first.graph_hash
    assert "layout" not in canonical_hypergraph_json(first)


def test_deduction_edge_closes_over_all_evidence_vertices() -> None:
    spec, trace = sources()
    graph = project_reasoning_hypergraph(spec, trace)
    deduction = next(item for item in graph.edges if item.edge_type is HyperedgeType.ASSIGNS)
    assert evidence_closure_failures(graph.vertices, graph.edges) == ()
    assert len(deduction.tail_vertex_ids) >= 5
    assert len(deduction.head_vertex_ids) == 3


def test_closure_validator_detects_a_missing_evidence_vertex() -> None:
    spec, trace = sources()
    graph = project_reasoning_hypergraph(spec, trace)
    edge = graph.edges[0].model_copy(
        update={"tail_vertex_ids": (*graph.edges[0].tail_vertex_ids, "deductra:vertex:missing")}
    )
    failures = evidence_closure_failures(graph.vertices, (edge, *graph.edges[1:]))
    assert failures == (f"{edge.edge_id}:deductra:vertex:missing",)


def test_projection_rejects_mismatched_puzzle_revision() -> None:
    spec, trace = sources()
    mismatched = trace.model_copy(update={"puzzle_revision_id": "deductra:revision:other"})
    with pytest.raises(HypergraphProjectionError, match="revisions"):
        project_reasoning_hypergraph(spec, mismatched)


def test_checked_in_hypergraph_schema_is_current() -> None:
    path = ROOT / "schemas" / "reasoning-hypergraph-v1.schema.json"
    assert path.read_text(encoding="utf-8") == rendered_reasoning_hypergraph_json_schema()
