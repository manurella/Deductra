"""Acceptance evidence for the Logic Grid reference triad."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from deductra.domain.atoms import AssignmentAtom
from deductra.domain.constraints import ArithmeticConstraint
from deductra.domain.expressions import Equal, VariableReference
from deductra.domain.serialization import canonical_sha256
from deductra.families.logic_grid import (
    GALLERY_OPENING_SOLUTION,
    HARBOR_MORNING_SOLUTION,
    OBSERVATORY_ROTATION_SOLUTION,
    LogicGridSpec,
    check_logic_grid_solution,
    gallery_opening,
    harbor_morning,
    logic_grid_goldens,
    logic_grid_rules,
    observatory_rotation,
)
from deductra.reasoning import (
    HumanReasoningEngine,
    HumanSolveContext,
    HumanSolveStatus,
    ProducerRef,
    create_initial_state,
)
from deductra.verification import (
    AssignmentNegation,
    CpSatProofBackend,
    CrossVerificationCoordinator,
    ProofObligation,
    VerificationStatus,
    VerifiedRuleAuthority,
    Z3ProofBackend,
)

type _PuzzleFactory = Callable[[], LogicGridSpec]

_CASES = (
    (harbor_morning, HARBOR_MORNING_SOLUTION, "easy", "3x3", 4),
    (gallery_opening, GALLERY_OPENING_SOLUTION, "medium", "4x4", 9),
    (observatory_rotation, OBSERVATORY_ROTATION_SOLUTION, "hard", "5x5", 16),
)


def _without_clue(puzzle: LogicGridSpec, constraint_id: str) -> LogicGridSpec:
    payload = puzzle.model_dump()
    payload["constraints"] = tuple(
        constraint
        for constraint in payload["constraints"]
        if constraint["constraint_id"] != constraint_id
    )
    payload["clues"] = tuple(
        clue for clue in payload["clues"] if constraint_id not in clue["constraint_ids"]
    )
    return LogicGridSpec.model_validate(payload)


def _alternative_without(
    puzzle: LogicGridSpec,
    solution: tuple[AssignmentAtom, ...],
    constraint: ArithmeticConstraint,
) -> tuple[AssignmentAtom, ...]:
    expression = constraint.expression
    assert isinstance(expression, Equal)
    assert isinstance(expression.left, VariableReference)
    target_id = expression.left.variable_id
    category = next(item for item in puzzle.categories if target_id in item.variable_ids)
    target = next(item for item in solution if item.variable_id == target_id)
    omitted_id = category.variable_ids[-1]
    omitted = next(item for item in solution if item.variable_id == omitted_id)
    return tuple(
        AssignmentAtom(variable_id=item.variable_id, value_id=omitted.value_id)
        if item.variable_id == target_id
        else AssignmentAtom(variable_id=item.variable_id, value_id=target.value_id)
        if item.variable_id == omitted_id
        else item
        for item in solution
    )


@pytest.mark.parametrize(
    ("factory", "solution", "difficulty", "dimensions", "clue_count"),
    _CASES,
)
def test_reference_identity_content_and_solution_are_fixed(
    factory: _PuzzleFactory,
    solution: tuple[AssignmentAtom, ...],
    difficulty: str,
    dimensions: str,
    clue_count: int,
) -> None:
    puzzle = factory()
    size = int(dimensions[0])
    assert puzzle.identity.source_kind == "golden"
    assert puzzle.identity.metadata["difficulty"] == difficulty
    assert puzzle.identity.metadata["dimensions"] == dimensions
    assert len(puzzle.categories) == size
    assert all(len(category.variable_ids) == size for category in puzzle.categories)
    assert len(puzzle.clues) == clue_count
    assert len(solution) == size * size
    assert check_logic_grid_solution(puzzle, solution).accepted


def test_reference_hashes_and_order_are_deterministic() -> None:
    first = logic_grid_goldens()
    second = logic_grid_goldens()
    assert first == second
    assert tuple(item.identity.title for item in first) == (
        "Harbor Morning",
        "Gallery Opening",
        "Observatory Rotation",
    )
    assert tuple(canonical_sha256(item) for item in first) == (
        "0c5ee10b25831a5712536b38126d4bbae110a0a9ba6b3b5f06d927dc4bafb521",
        "cf056efd2d80823e37e1b9bc24913878421ed2852e197ff9a82c840faff40578",
        "c1aa7f1b59d3c2b0596263d0aa5e643d5c8ad1963f66675961f7345584dc6943",
    )


@pytest.mark.parametrize(("factory", "solution", "_d", "_x", "_c"), _CASES)
def test_independent_checker_rejects_an_incorrect_bijection(
    factory: _PuzzleFactory,
    solution: tuple[AssignmentAtom, ...],
    _d: str,
    _x: str,
    _c: int,
) -> None:
    puzzle = factory()
    category = puzzle.categories[-1]
    first_id, second_id = category.variable_ids[:2]
    by_id = {item.variable_id: item for item in solution}
    wrong = tuple(
        AssignmentAtom(variable_id=item.variable_id, value_id=by_id[second_id].value_id)
        if item.variable_id == first_id
        else AssignmentAtom(variable_id=item.variable_id, value_id=by_id[first_id].value_id)
        if item.variable_id == second_id
        else item
        for item in solution
    )
    result = check_logic_grid_solution(puzzle, wrong)
    assert not result.accepted
    assert result.violations


def test_checker_reports_boundary_errors_deterministically() -> None:
    puzzle = harbor_morning()
    unknown = AssignmentAtom(
        variable_id="deductra:variable:harbor-morning:unknown:1",
        value_id=HARBOR_MORNING_SOLUTION[0].value_id,
    )
    result = check_logic_grid_solution(
        puzzle,
        (*HARBOR_MORNING_SOLUTION[:-1], HARBOR_MORNING_SOLUTION[0], unknown),
    )
    assert not result.accepted
    assert result.violations == (
        f"duplicate_assignment:{HARBOR_MORNING_SOLUTION[0].variable_id}",
        f"unknown_variable:{unknown.variable_id}",
        f"missing_assignment:{HARBOR_MORNING_SOLUTION[-1].variable_id}",
    )


@pytest.mark.parametrize(("factory", "solution", "_d", "_x", "_c"), _CASES)
def test_every_presentation_clue_is_necessary_for_uniqueness(
    factory: _PuzzleFactory,
    solution: tuple[AssignmentAtom, ...],
    _d: str,
    _x: str,
    _c: int,
) -> None:
    puzzle = factory()
    clue_constraints = tuple(
        item for item in puzzle.constraints if isinstance(item, ArithmeticConstraint)
    )
    for constraint in clue_constraints:
        reduced = _without_clue(puzzle, constraint.constraint_id)
        alternative = _alternative_without(puzzle, solution, constraint)
        assert alternative != solution
        assert check_logic_grid_solution(reduced, solution).accepted
        assert check_logic_grid_solution(reduced, alternative).accepted


@pytest.mark.parametrize(("factory", "solution", "_d", "_x", "_c"), _CASES)
def test_both_backends_prove_the_complete_solution_is_unique(
    factory: _PuzzleFactory,
    solution: tuple[AssignmentAtom, ...],
    _d: str,
    _x: str,
    _c: int,
) -> None:
    puzzle = factory()
    source = create_initial_state(
        puzzle,
        state_id=f"deductra:state:{puzzle.identity.puzzle_id.rsplit(':', 1)[1]}:initial",
        branch_id=f"deductra:branch:{puzzle.identity.puzzle_id.rsplit(':', 1)[1]}:root",
        sequence_no=0,
    )
    coordinator = CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
    given_ids = {item.variable_id for item in puzzle.givens if isinstance(item, AssignmentAtom)}
    for assignment in solution:
        if assignment.variable_id in given_ids:
            continue
        obligation = ProofObligation(
            obligation_id=(f"deductra:obligation:logic-grid-golden:{canonical_sha256(assignment)}"),
            puzzle_revision_id=source.puzzle_revision_id,
            source_state_hash=source.state_hash,
            claimed_conclusions=(assignment,),
            negated_claim=AssignmentNegation(
                variable_id=assignment.variable_id,
                value_id=assignment.value_id,
            ),
        )
        decision = coordinator.verify(puzzle, source, obligation)
        assert decision.status is VerificationStatus.CROSS_VERIFIED
        assert {certificate.result for certificate in decision.certificates} == {"unsat"}


@pytest.mark.parametrize(("factory", "solution", "_d", "_x", "_c"), _CASES)
def test_verified_human_solve_is_complete_and_deterministic(
    factory: _PuzzleFactory,
    solution: tuple[AssignmentAtom, ...],
    _d: str,
    _x: str,
    _c: int,
) -> None:
    puzzle = factory()
    slug = puzzle.identity.puzzle_id.rsplit(":", 1)[1]
    source = create_initial_state(
        puzzle,
        state_id=f"deductra:state:{slug}:initial",
        branch_id=f"deductra:branch:{slug}:root",
        sequence_no=0,
    )
    engine = HumanReasoningEngine(
        logic_grid_rules(),
        VerifiedRuleAuthority(
            CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
        ),
    )
    context = HumanSolveContext(
        trace_id=f"deductra:trace:{slug}:canonical",
        correlation_id=f"deductra:correlation:{slug}:canonical",
        producer=ProducerRef(
            producer_id="deductra:producer:logic-grid-rules",
            kind="rule_engine",
            version="1.0.0",
        ),
        occurred_at=puzzle.identity.created_at,
        previous_event_hash="4" * 64,
    )
    first = engine.solve(puzzle, source, context)
    second = engine.solve(puzzle, source, context)

    assert first == second
    assert first.status is HumanSolveStatus.SOLVED
    assert first.final_state_hash != source.state_hash
    assert first.attempts
    assert all(attempt.verification_status.value == "cross_verified" for attempt in first.attempts)
