"""CR-003 acceptance tests for immutable state, replay, branches, and snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint
from deductra.domain.puzzle import DisplaySpec, ProvenanceBundle, PuzzleIdentity, PuzzleSpec
from deductra.domain.serialization import canonical_json
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.memory.snapshots import create_snapshot, verify_snapshot
from deductra.reasoning.branches import create_branch_projection, reduce_branch_projection
from deductra.reasoning.events import (
    BranchClosed,
    BranchOpened,
    CandidatesEliminated,
    ContradictionDetected,
    EventEnvelope,
    InitialStateCreated,
    ProducerRef,
    ReasoningEventPayload,
    TraceStarted,
    ValueAssigned,
)
from deductra.reasoning.integrity import GENESIS_EVENT_HASH, seal_event
from deductra.reasoning.reducer import (
    SearchDisclosureError,
    StateConflictError,
    UnsupportedStateEventError,
    reduce_state,
    replay_projection,
)
from deductra.reasoning.schema import rendered_puzzle_state_json_schema
from deductra.reasoning.state import build_state, create_initial_state, validate_state

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
ROOT_BRANCH = "deductra:branch:root"
SEARCH_BRANCH = "deductra:branch:search:1"
PRODUCER = ProducerRef(
    producer_id="deductra:producer:test",
    kind="system",
    version="1.0.0",
)


def puzzle_spec() -> PuzzleSpec:
    """Build a small unsolved puzzle with one cross-variable invariant."""
    values = tuple(
        DomainValue(value_id=f"deductra:value:{label}", label=label.upper())
        for label in ("a", "b", "c")
    )
    return PuzzleSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:state-test",
            revision_id="deductra:revision:state-test:1",
            family_id="state-test",
            schema_version="1.0.0",
            title="State reducer test",
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
                variable_id=f"deductra:variable:{label}",
                label=label.upper(),
                domain_id="deductra:domain:letters",
                role="answer",
            )
            for label in ("x", "y")
        ),
        constraints=(
            AllDifferentConstraint(
                constraint_id="deductra:constraint:distinct",
                label="Answers differ",
                variable_ids=("deductra:variable:x", "deductra:variable:y"),
            ),
        ),
        clues=(),
        givens=(),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def initial_state():
    return create_initial_state(
        puzzle_spec(),
        state_id="deductra:state:genesis",
        branch_id=ROOT_BRANCH,
        sequence_no=1,
    )


def sealed(
    sequence_no: int,
    previous_hash: str,
    payload: ReasoningEventPayload,
    *,
    branch_id: str = ROOT_BRANCH,
    puzzle_revision_id: str = "deductra:revision:state-test:1",
) -> EventEnvelope:
    return seal_event(
        event_id=f"deductra:event:state:{sequence_no}",
        trace_id="deductra:trace:state-test",
        puzzle_revision_id=puzzle_revision_id,
        branch_id=branch_id,
        sequence_no=sequence_no,
        schema_version="1.0.0",
        occurred_at=NOW,
        producer=PRODUCER,
        correlation_id="deductra:correlation:state-test",
        previous_event_hash=previous_hash,
        payload=payload,
    )


def genesis_events():
    state = initial_state()
    started = sealed(0, GENESIS_EVENT_HASH, TraceStarted(puzzle_spec_hash="a" * 64))
    created = sealed(1, started.event_hash, InitialStateCreated(state_hash=state.state_hash))
    return state, [started, created]


def test_initial_state_is_immutable_valid_and_schema_stable() -> None:
    state = initial_state()
    assert validate_state(state, puzzle_spec()).valid
    with pytest.raises(ValidationError, match="Instance is frozen"):
        state.solved = True
    with pytest.raises(TypeError):
        mutable = cast(dict[str, frozenset[str]], state.candidate_domains)
        mutable["deductra:variable:z"] = frozenset({"deductra:value:a"})

    schema_path = REPOSITORY_ROOT / "schemas" / "puzzle-state-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == rendered_puzzle_state_json_schema()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"candidate_domains": {}}, "at least one variable"),
        (
            {
                "candidate_domains": {
                    "deductra:variable:x": [],
                    "deductra:variable:y": ["deductra:value:a"],
                }
            },
            "explicit contradiction",
        ),
        (
            {
                "asserted_atoms": [
                    {
                        "kind": "assignment",
                        "variable_id": "deductra:variable:x",
                        "value_id": "deductra:value:a",
                    }
                ],
                "rejected_atoms": [
                    {
                        "kind": "assignment",
                        "variable_id": "deductra:variable:x",
                        "value_id": "deductra:value:a",
                    }
                ],
            },
            "must not overlap",
        ),
        (
            {
                "contradiction_ids": [
                    "deductra:contradiction:duplicate",
                    "deductra:contradiction:duplicate",
                ]
            },
            "must be unique",
        ),
        (
            {
                "candidate_domains": {
                    "deductra:variable:x": ["deductra:value:a"],
                    "deductra:variable:y": [
                        "deductra:value:a",
                        "deductra:value:b",
                    ],
                }
            },
            "assignment projection",
        ),
        ({"solved": True}, "solved must match"),
        ({"state_hash": "0" * 64}, "state_hash"),
    ],
)
def test_state_contract_rejects_structural_corruption(
    change: dict[str, object],
    message: str,
) -> None:
    payload = initial_state().model_dump(mode="json")
    payload.update(change)
    with pytest.raises(ValidationError, match=message):
        type(initial_state()).model_validate_json(canonical_json(payload))


def test_invariant_validator_reports_cross_contract_drift() -> None:
    state = initial_state()
    assignment_a = AssignmentAtom(
        variable_id="deductra:variable:x",
        value_id="deductra:value:a",
    )
    assignment_b = AssignmentAtom(
        variable_id="deductra:variable:x",
        value_id="deductra:value:b",
    )
    unknown_assignment = AssignmentAtom(
        variable_id="deductra:variable:unknown",
        value_id="deductra:value:unknown",
    )
    exclusion = ExclusionAtom(
        variable_id="deductra:variable:x",
        value_id="deductra:value:a",
    )
    drifted = state.model_copy(
        update={
            "puzzle_revision_id": "deductra:revision:other:1",
            "candidate_domains": {
                "deductra:variable:x": frozenset(
                    {
                        "deductra:value:a",
                        "deductra:value:b",
                        "deductra:value:outside",
                    }
                )
            },
            "asserted_atoms": frozenset(
                (
                    assignment_a,
                    assignment_b,
                    unknown_assignment,
                    exclusion,
                )
            ),
            "active_constraint_ids": frozenset({"deductra:constraint:unknown"}),
        }
    )
    violations = validate_state(drifted, puzzle_spec()).violations
    assert {
        "puzzle_revision_mismatch",
        "candidate_variable_mismatch",
        "candidate_outside_domain:deductra:variable:x",
        "conflicting_assignment:deductra:variable:x",
        "assignment_candidate_mismatch:deductra:variable:x",
        "assignment_outside_domain:deductra:variable:unknown",
        "assignment_candidate_mismatch:deductra:variable:unknown",
        "excluded_candidate_present:deductra:variable:x",
        "unknown_active_constraint",
    } <= set(violations)


def test_reducer_is_byte_deterministic_and_does_not_mutate_input() -> None:
    state = initial_state()
    payload = CandidatesEliminated(
        variable_id="deductra:variable:x",
        value_ids=("deductra:value:c",),
        source_state_hash=state.state_hash,
        result_state_id="deductra:state:2",
        origin="human_rule",
    )
    event = sealed(2, "b" * 64, payload)

    first = reduce_state(state, event)
    second = reduce_state(state, event)

    assert canonical_json(first) == canonical_json(second)
    assert state.candidate_domains["deductra:variable:x"] == frozenset(
        {"deductra:value:a", "deductra:value:b", "deductra:value:c"}
    )
    assert first.candidate_domains["deductra:variable:x"] == frozenset(
        {"deductra:value:a", "deductra:value:b"}
    )


def test_invariant_validator_detects_all_different_conflicts() -> None:
    state = initial_state()
    assignment_x = AssignmentAtom(
        variable_id="deductra:variable:x",
        value_id="deductra:value:a",
    )
    assignment_y = AssignmentAtom(
        variable_id="deductra:variable:y",
        value_id="deductra:value:a",
    )
    invalid = build_state(
        state_id="deductra:state:invalid",
        puzzle_revision_id=state.puzzle_revision_id,
        sequence_no=2,
        branch_id=state.branch_id,
        candidate_domains={
            "deductra:variable:x": frozenset({"deductra:value:a"}),
            "deductra:variable:y": frozenset({"deductra:value:a"}),
        },
        asserted_atoms=frozenset(
            {assignment_x, assignment_y}  # pyright: ignore[reportUnhashable]
        ),
        rejected_atoms=frozenset(),
        active_constraint_ids=state.active_constraint_ids,
        contradiction_ids=(),
    )
    validation = validate_state(invalid, puzzle_spec())
    assert validation.violations == ("all_different_violation:deductra:constraint:distinct",)


def test_reducer_rejects_wrong_source_state() -> None:
    state = initial_state()
    event = sealed(
        2,
        "b" * 64,
        ValueAssigned(
            variable_id="deductra:variable:x",
            value_id="deductra:value:a",
            source_state_hash="f" * 64,
            result_state_id="deductra:state:2",
            origin="human_rule",
        ),
    )
    with pytest.raises(StateConflictError, match="source_state_hash"):
        reduce_state(state, event)


def test_reducer_rejects_invalid_identity_order_and_event_kind() -> None:
    state = initial_state()
    payload = ValueAssigned(
        variable_id="deductra:variable:x",
        value_id="deductra:value:a",
        source_state_hash=state.state_hash,
        result_state_id="deductra:state:2",
        origin="human_rule",
    )
    valid = sealed(2, "b" * 64, payload)

    with pytest.raises(StateConflictError, match="integrity"):
        reduce_state(state, valid.model_copy(update={"event_hash": "0" * 64}))
    with pytest.raises(StateConflictError, match="puzzle revision"):
        reduce_state(
            state,
            sealed(
                2,
                "b" * 64,
                payload,
                puzzle_revision_id="deductra:revision:other:1",
            ),
        )
    with pytest.raises(StateConflictError, match="branch"):
        reduce_state(state, sealed(2, "b" * 64, payload, branch_id=SEARCH_BRANCH))
    with pytest.raises(StateConflictError, match="newer"):
        reduce_state(state, sealed(1, "b" * 64, payload))
    with pytest.raises(UnsupportedStateEventError):
        reduce_state(
            state,
            sealed(2, "b" * 64, TraceStarted(puzzle_spec_hash="a" * 64)),
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            CandidatesEliminated(
                variable_id="deductra:variable:unknown",
                value_ids=("deductra:value:a",),
                source_state_hash=initial_state().state_hash,
                result_state_id="deductra:state:invalid:unknown",
                origin="human_rule",
            ),
            "unknown variable",
        ),
        (
            CandidatesEliminated(
                variable_id="deductra:variable:x",
                value_ids=("deductra:value:unknown",),
                source_state_hash=initial_state().state_hash,
                result_state_id="deductra:state:invalid:value",
                origin="human_rule",
            ),
            "unavailable values",
        ),
        (
            CandidatesEliminated(
                variable_id="deductra:variable:x",
                value_ids=(
                    "deductra:value:a",
                    "deductra:value:b",
                    "deductra:value:c",
                ),
                source_state_hash=initial_state().state_hash,
                result_state_id="deductra:state:invalid:empty",
                origin="human_rule",
            ),
            "cannot empty",
        ),
        (
            ValueAssigned(
                variable_id="deductra:variable:x",
                value_id="deductra:value:unknown",
                source_state_hash=initial_state().state_hash,
                result_state_id="deductra:state:invalid:assignment",
                origin="human_rule",
            ),
            "outside",
        ),
    ],
)
def test_reducer_rejects_invalid_candidate_changes(
    payload: ReasoningEventPayload,
    message: str,
) -> None:
    with pytest.raises(StateConflictError, match=message):
        reduce_state(initial_state(), sealed(2, "b" * 64, payload))


def test_reducer_rejects_duplicate_contradiction_identity() -> None:
    state = initial_state()
    first = sealed(
        2,
        "b" * 64,
        ContradictionDetected(
            contradiction_id="deductra:contradiction:duplicate",
            source_state_hash=state.state_hash,
            result_state_id="deductra:state:contradicted:2",
            category="test",
        ),
    )
    contradicted = reduce_state(state, first)
    repeated = sealed(
        3,
        first.event_hash,
        ContradictionDetected(
            contradiction_id="deductra:contradiction:duplicate",
            source_state_hash=contradicted.state_hash,
            result_state_id="deductra:state:contradicted:3",
            category="test",
        ),
    )
    with pytest.raises(StateConflictError, match="already exists"):
        reduce_state(contradicted, repeated)


def test_replay_retains_contradicted_branch_after_parent_continues() -> None:
    genesis, events = genesis_events()
    direct = create_branch_projection(genesis)

    opened = sealed(
        2,
        events[-1].event_hash,
        BranchOpened(
            parent_branch_id=ROOT_BRANCH,
            opened_from_state_hash=genesis.state_hash,
            assumption=AssignmentAtom(
                variable_id="deductra:variable:x",
                value_id="deductra:value:a",
            ),
            method="search",
            result_state_id="deductra:state:search:2",
        ),
        branch_id=SEARCH_BRANCH,
    )
    events.append(opened)
    direct = reduce_branch_projection(direct, opened)

    contradicted = sealed(
        3,
        events[-1].event_hash,
        ContradictionDetected(
            contradiction_id="deductra:contradiction:1",
            source_state_hash=direct.active_state.state_hash,
            result_state_id="deductra:state:search:3",
            category="assumption_conflict",
        ),
        branch_id=SEARCH_BRANCH,
    )
    events.append(contradicted)
    direct = reduce_branch_projection(direct, contradicted)

    closed = sealed(
        4,
        events[-1].event_hash,
        BranchClosed(
            source_state_hash=direct.active_state.state_hash,
            status="contradicted",
        ),
        branch_id=SEARCH_BRANCH,
    )
    events.append(closed)
    direct = reduce_branch_projection(direct, closed)

    parent_continues = sealed(
        5,
        events[-1].event_hash,
        CandidatesEliminated(
            variable_id="deductra:variable:x",
            value_ids=("deductra:value:a",),
            source_state_hash=genesis.state_hash,
            result_state_id="deductra:state:root:5",
            origin="human_rule",
        ),
    )
    events.append(parent_continues)
    direct = reduce_branch_projection(direct, parent_continues)

    replayed = replay_projection(genesis, events)

    assert replayed == direct
    assert replayed.active_branch_id == ROOT_BRANCH
    assert replayed.record_for(SEARCH_BRANCH).status == "contradicted"
    assert replayed.state_for(SEARCH_BRANCH).contradiction_ids == ("deductra:contradiction:1",)
    assert replayed.state_for(ROOT_BRANCH).state_hash == direct.active_state.state_hash


def test_search_branch_rejects_human_rule_disclosure() -> None:
    genesis, events = genesis_events()
    projection = create_branch_projection(genesis)
    opened = sealed(
        2,
        events[-1].event_hash,
        BranchOpened(
            parent_branch_id=ROOT_BRANCH,
            opened_from_state_hash=genesis.state_hash,
            assumption=AssignmentAtom(
                variable_id="deductra:variable:x",
                value_id="deductra:value:a",
            ),
            method="search",
            result_state_id="deductra:state:search:2",
        ),
        branch_id=SEARCH_BRANCH,
    )
    projection = reduce_branch_projection(projection, opened)
    mislabeled = sealed(
        3,
        opened.event_hash,
        ValueAssigned(
            variable_id="deductra:variable:y",
            value_id="deductra:value:b",
            source_state_hash=projection.active_state.state_hash,
            result_state_id="deductra:state:search:3",
            origin="human_rule",
        ),
        branch_id=SEARCH_BRANCH,
    )
    with pytest.raises(SearchDisclosureError):
        reduce_branch_projection(projection, mislabeled)


def test_root_rejects_search_origin_and_destructive_close() -> None:
    genesis, events = genesis_events()
    projection = create_branch_projection(genesis)
    undisclosed_branch = sealed(
        2,
        events[-1].event_hash,
        CandidatesEliminated(
            variable_id="deductra:variable:x",
            value_ids=("deductra:value:c",),
            source_state_hash=genesis.state_hash,
            result_state_id="deductra:state:root:2",
            origin="search",
        ),
    )
    with pytest.raises(SearchDisclosureError, match="explicit search branch"):
        reduce_branch_projection(projection, undisclosed_branch)

    close_root = sealed(
        2,
        events[-1].event_hash,
        BranchClosed(source_state_hash=genesis.state_hash, status="abandoned"),
    )
    with pytest.raises(StateConflictError, match="root branch"):
        reduce_branch_projection(projection, close_root)

    unknown_branch = sealed(
        2,
        events[-1].event_hash,
        TraceStarted(puzzle_spec_hash="a" * 64),
        branch_id="deductra:branch:unknown",
    )
    with pytest.raises(StateConflictError, match="unknown retained branch"):
        reduce_branch_projection(projection, unknown_branch)


def test_exclusion_assumption_creates_a_separate_child_projection() -> None:
    genesis, events = genesis_events()
    projection = create_branch_projection(genesis)
    opened = sealed(
        2,
        events[-1].event_hash,
        BranchOpened(
            parent_branch_id=ROOT_BRANCH,
            opened_from_state_hash=genesis.state_hash,
            assumption=ExclusionAtom(
                variable_id="deductra:variable:x",
                value_id="deductra:value:c",
            ),
            method="assumption",
            result_state_id="deductra:state:assumption:2",
        ),
        branch_id=SEARCH_BRANCH,
    )
    branched = reduce_branch_projection(projection, opened)

    assert branched.active_state.candidate_domains["deductra:variable:x"] == frozenset(
        {"deductra:value:a", "deductra:value:b"}
    )
    assert projection.active_state == genesis


def test_replay_rejects_invalid_chain_and_genesis_mismatch() -> None:
    genesis, events = genesis_events()
    damaged = events[0].model_copy(update={"event_hash": "0" * 64})
    with pytest.raises(StateConflictError, match="event stream is invalid"):
        replay_projection(genesis, (damaged, events[1]))

    mismatched_genesis = sealed(
        1,
        events[0].event_hash,
        InitialStateCreated(state_hash="f" * 64),
    )
    with pytest.raises(StateConflictError, match="genesis state"):
        replay_projection(genesis, (events[0], mismatched_genesis))


def test_snapshot_corruption_is_detectable_without_becoming_authority() -> None:
    state, events = genesis_events()
    snapshot = create_snapshot(
        snapshot_id="deductra:snapshot:1",
        state=state,
        source_event_id=events[-1].event_id,
        source_event_hash=events[-1].event_hash,
    )
    assert verify_snapshot(snapshot)

    damaged = snapshot.model_copy(update={"source_event_id": "deductra:event:state:damaged"})
    assert not verify_snapshot(damaged)
    with pytest.raises(ValidationError, match="snapshot_hash"):
        type(snapshot).model_validate_json(damaged.model_dump_json())
