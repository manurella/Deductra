"""Acceptance evidence for the Logic Equations Golden Easy puzzle."""

from __future__ import annotations

from itertools import permutations

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import ArithmeticConstraint
from deductra.domain.serialization import canonical_sha256
from deductra.families.logic_equations import (
    FOUR_SIGILS_SOLUTION,
    LogicEquationsSpec,
    check_logic_equations_solution,
    four_sigils,
    logic_equations_rules,
)
from deductra.reasoning import (
    HumanReasoningEngine,
    HumanSolveContext,
    HumanSolveStatus,
    ProducerRef,
    PuzzleState,
    create_initial_state,
)
from deductra.reasoning.events import CandidatesEliminated, ValueAssigned
from deductra.verification import (
    AssignmentNegation,
    CpSatProofBackend,
    CrossVerificationCoordinator,
    EliminationNegation,
    ProofObligation,
    VerificationStatus,
    VerifiedRuleAuthority,
    Z3ProofBackend,
)


def _initial_state() -> PuzzleState:
    puzzle = four_sigils()
    return create_initial_state(
        puzzle,
        state_id="deductra:state:four-sigils:initial",
        branch_id="deductra:branch:four-sigils:root",
        sequence_no=0,
    )


def _coordinator() -> CrossVerificationCoordinator:
    return CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))


def _context() -> HumanSolveContext:
    return HumanSolveContext(
        trace_id="deductra:trace:four-sigils:canonical",
        correlation_id="deductra:correlation:four-sigils:canonical",
        producer=ProducerRef(
            producer_id="deductra:producer:logic-equations-rules",
            kind="rule_engine",
            version="1.0.0",
        ),
        occurred_at=four_sigils().identity.created_at,
        previous_event_hash="4" * 64,
    )


def _obligation(
    source_state: PuzzleState,
    conclusion: AssignmentAtom | ExclusionAtom,
) -> ProofObligation:
    return ProofObligation(
        obligation_id=(
            f"deductra:obligation:four-sigils:{conclusion.variable_id.rsplit(':', 1)[1]}"
        ),
        puzzle_revision_id=source_state.puzzle_revision_id,
        source_state_hash=source_state.state_hash,
        claimed_conclusions=(conclusion,),
        negated_claim=(
            AssignmentNegation(
                variable_id=conclusion.variable_id,
                value_id=conclusion.value_id,
            )
            if isinstance(conclusion, AssignmentAtom)
            else EliminationNegation(
                variable_id=conclusion.variable_id,
                value_id=conclusion.value_id,
            )
        ),
    )


def _accepted_assignments(puzzle: LogicEquationsSpec) -> tuple[tuple[AssignmentAtom, ...], ...]:
    value_ids = tuple(value.value_id for value in puzzle.domains[0].values)
    candidates = (
        tuple(
            AssignmentAtom(variable_id=variable.variable_id, value_id=value_id)
            for variable, value_id in zip(puzzle.variables, ordered_values, strict=True)
        )
        for ordered_values in permutations(value_ids)
    )
    return tuple(
        assignments
        for assignments in candidates
        if check_logic_equations_solution(puzzle, assignments).accepted
    )


def _without_clue(puzzle: LogicEquationsSpec, constraint_id: str) -> LogicEquationsSpec:
    payload = puzzle.model_dump()
    payload["constraints"] = tuple(
        constraint
        for constraint in payload["constraints"]
        if constraint["constraint_id"] != constraint_id
    )
    payload["clues"] = tuple(
        clue for clue in payload["clues"] if constraint_id not in clue["constraint_ids"]
    )
    return LogicEquationsSpec.model_validate(payload)


def test_golden_identity_and_content_are_fixed() -> None:
    puzzle = four_sigils()
    assert puzzle.identity.title == "The Four Sigils"
    assert puzzle.identity.source_kind == "golden"
    assert puzzle.identity.metadata["difficulty"] == "easy"
    assert len(puzzle.variables) == 4
    assert len(puzzle.clues) == 3
    assert all(not clue.instructional_redundancy for clue in puzzle.clues)
    assert canonical_sha256(puzzle) == (
        "768616cd184f11746b27aadbd3e3813c1866bdb5734e8814ca0d7f86941c57be"
    )


def test_independent_checker_accepts_only_the_expected_solution() -> None:
    puzzle = four_sigils()
    accepted = _accepted_assignments(puzzle)
    assert accepted == (FOUR_SIGILS_SOLUTION,)

    wrong = (
        *FOUR_SIGILS_SOLUTION[:-2],
        AssignmentAtom(
            variable_id=FOUR_SIGILS_SOLUTION[2].variable_id,
            value_id=FOUR_SIGILS_SOLUTION[3].value_id,
        ),
        AssignmentAtom(
            variable_id=FOUR_SIGILS_SOLUTION[3].variable_id,
            value_id=FOUR_SIGILS_SOLUTION[2].value_id,
        ),
    )
    check = check_logic_equations_solution(puzzle, wrong)
    assert not check.accepted
    assert check.violations


def test_every_presentation_clue_is_necessary_for_uniqueness() -> None:
    puzzle = four_sigils()
    arithmetic_ids = tuple(
        constraint.constraint_id
        for constraint in puzzle.constraints
        if isinstance(constraint, ArithmeticConstraint)
    )
    assert len(_accepted_assignments(puzzle)) == 1
    assert all(
        len(_accepted_assignments(_without_clue(puzzle, constraint_id))) > 1
        for constraint_id in arithmetic_ids
    )


def test_both_backends_prove_the_complete_solution_is_unique() -> None:
    puzzle = four_sigils()
    source = _initial_state()
    for assignment in FOUR_SIGILS_SOLUTION:
        decision = _coordinator().verify(puzzle, source, _obligation(source, assignment))
        assert decision.status is VerificationStatus.CROSS_VERIFIED
        assert {certificate.result for certificate in decision.certificates} == {"unsat"}


def test_canonical_human_solve_is_complete_verified_and_deterministic() -> None:
    puzzle = four_sigils()
    source = _initial_state()
    engine = HumanReasoningEngine(
        logic_equations_rules(),
        VerifiedRuleAuthority(_coordinator()),
    )
    first = engine.solve(puzzle, source, _context())
    second = engine.solve(puzzle, source, _context())

    assert first == second
    assert first.status is HumanSolveStatus.SOLVED
    assert first.events
    assert all(attempt.verification_status.value == "cross_verified" for attempt in first.attempts)
    assert {attempt.rule.rule_id.rsplit(":", 1)[1] for attempt in first.attempts} >= {
        "direct_relation",
        "all_different",
        "arithmetic",
    }
    assert any(
        isinstance(conclusion, ExclusionAtom)
        for attempt in first.attempts
        for conclusion in attempt.conclusions
    )
    assert all(
        isinstance(event.payload, (CandidatesEliminated, ValueAssigned))
        and event.payload.origin == "human_rule"
        for event in first.events
    )
