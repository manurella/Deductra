"""Pure deterministic reducers for immutable puzzle and branch projections."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.reasoning.events import (
    BranchOpened,
    CandidatesEliminated,
    ContradictionDetected,
    EventEnvelope,
    InitialStateCreated,
    ValueAssigned,
)
from deductra.reasoning.integrity import verify_chain, verify_event
from deductra.reasoning.state import PuzzleState, build_state

if TYPE_CHECKING:
    from deductra.reasoning.branches import BranchProjection


class StateReductionError(ValueError):
    """Base error for events that cannot validly reduce a state projection."""


class StateConflictError(StateReductionError):
    """An event does not continue the supplied state projection."""


class UnsupportedStateEventError(StateReductionError):
    """An event has no state-reduction semantics in CR-003."""


class SearchDisclosureError(StateReductionError):
    """A search-derived mutation is mislabeled or applied outside a search branch."""


type StateMutation = CandidatesEliminated | ValueAssigned | ContradictionDetected


def _validate_reduction(previous: PuzzleState, event: EventEnvelope) -> StateMutation:
    if not verify_event(event):
        raise StateConflictError("event integrity verification failed")
    if event.puzzle_revision_id != previous.puzzle_revision_id:
        raise StateConflictError("event puzzle revision does not match the state")
    if event.branch_id != previous.branch_id:
        raise StateConflictError("event branch does not match the state")
    if event.sequence_no <= previous.sequence_no:
        raise StateConflictError("event sequence must be newer than the branch state")
    if not isinstance(event.payload, (CandidatesEliminated, ValueAssigned, ContradictionDetected)):
        raise UnsupportedStateEventError(f"{event.event_type} does not reduce PuzzleState")
    if event.payload.source_state_hash != previous.state_hash:
        raise StateConflictError("event source_state_hash does not match the state")
    return event.payload


def reduce_state(previous: PuzzleState, event: EventEnvelope) -> PuzzleState:
    """Apply one verified state-changing event without mutating its input."""
    payload = _validate_reduction(previous, event)
    candidates = {
        variable_id: set(value_ids) for variable_id, value_ids in previous.candidate_domains.items()
    }
    asserted = set(previous.asserted_atoms)
    contradictions = previous.contradiction_ids

    if isinstance(payload, CandidatesEliminated):
        current = candidates.get(payload.variable_id)
        if current is None:
            raise StateConflictError("candidate elimination references an unknown variable")
        unknown = set(payload.value_ids) - current
        if unknown:
            raise StateConflictError("candidate elimination references unavailable values")
        remaining = current - set(payload.value_ids)
        if not remaining:
            raise StateConflictError(
                "candidate elimination cannot empty a non-contradictory domain"
            )
        candidates[payload.variable_id] = remaining
        asserted.update(
            ExclusionAtom(variable_id=payload.variable_id, value_id=value_id)
            for value_id in payload.value_ids
        )
        result_state_id = payload.result_state_id
    elif isinstance(payload, ValueAssigned):
        current = candidates.get(payload.variable_id)
        if current is None or payload.value_id not in current:
            raise StateConflictError("assignment is outside the current candidate domain")
        candidates[payload.variable_id] = {payload.value_id}
        asserted.add(AssignmentAtom(variable_id=payload.variable_id, value_id=payload.value_id))
        asserted.update(
            ExclusionAtom(variable_id=payload.variable_id, value_id=value_id)
            for value_id in current
            if value_id != payload.value_id
        )
        result_state_id = payload.result_state_id
    else:
        if payload.contradiction_id in contradictions:
            raise StateConflictError("contradiction identifier already exists")
        contradictions = (*contradictions, payload.contradiction_id)
        result_state_id = payload.result_state_id

    for variable_id, value_ids in candidates.items():
        if len(value_ids) == 1:
            asserted.add(AssignmentAtom(variable_id=variable_id, value_id=next(iter(value_ids))))

    return build_state(
        state_id=result_state_id,
        puzzle_revision_id=previous.puzzle_revision_id,
        sequence_no=event.sequence_no,
        branch_id=previous.branch_id,
        candidate_domains={key: frozenset(value) for key, value in candidates.items()},
        asserted_atoms=frozenset(asserted),
        rejected_atoms=previous.rejected_atoms,
        active_constraint_ids=previous.active_constraint_ids,
        contradiction_ids=contradictions,
    )


def derive_branch_state(
    parent: PuzzleState,
    event: EventEnvelope,
    payload: BranchOpened,
) -> PuzzleState:
    """Create one child branch projection while retaining the parent unchanged."""
    if payload.opened_from_state_hash != parent.state_hash:
        raise StateConflictError("branch source hash does not match its parent state")
    candidates = {
        variable_id: set(value_ids) for variable_id, value_ids in parent.candidate_domains.items()
    }
    asserted = set(parent.asserted_atoms)
    assumption: Atom = payload.assumption
    if isinstance(assumption, AssignmentAtom):
        current = candidates.get(assumption.variable_id)
        if current is None or assumption.value_id not in current:
            raise StateConflictError("branch assignment is outside the current candidate domain")
        candidates[assumption.variable_id] = {assumption.value_id}
    elif isinstance(assumption, ExclusionAtom):
        current = candidates.get(assumption.variable_id)
        if current is None or assumption.value_id not in current:
            raise StateConflictError("branch exclusion is outside the current candidate domain")
        current.remove(assumption.value_id)
        if not current:
            raise StateConflictError("branch assumption cannot empty a candidate domain")
    asserted.add(assumption)
    for variable_id, value_ids in candidates.items():
        if len(value_ids) == 1:
            asserted.add(AssignmentAtom(variable_id=variable_id, value_id=next(iter(value_ids))))

    return build_state(
        state_id=payload.result_state_id,
        puzzle_revision_id=parent.puzzle_revision_id,
        sequence_no=event.sequence_no,
        branch_id=event.branch_id,
        candidate_domains={key: frozenset(value) for key, value in candidates.items()},
        asserted_atoms=frozenset(asserted),
        rejected_atoms=parent.rejected_atoms,
        active_constraint_ids=parent.active_constraint_ids,
        contradiction_ids=(),
    )


def replay_projection(
    genesis: PuzzleState,
    events: Iterable[EventEnvelope],
) -> BranchProjection:
    """Rebuild all retained branches from a verified canonical event stream."""
    from deductra.reasoning.branches import create_branch_projection, reduce_branch_projection

    ordered = tuple(events)
    verification = verify_chain(ordered)
    if not verification.valid:
        raise StateConflictError(
            f"event stream is invalid at sequence {verification.first_invalid_sequence}"
        )
    genesis_event = next(
        (event for event in ordered if event.sequence_no == genesis.sequence_no),
        None,
    )
    if (
        genesis_event is None
        or genesis_event.branch_id != genesis.branch_id
        or not isinstance(genesis_event.payload, InitialStateCreated)
        or genesis_event.payload.state_hash != genesis.state_hash
    ):
        raise StateConflictError("genesis state does not match its InitialStateCreated event")

    projection = create_branch_projection(genesis)
    for event in ordered:
        if event.sequence_no > genesis.sequence_no:
            projection = reduce_branch_projection(projection, event)
    return projection
