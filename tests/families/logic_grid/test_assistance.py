"""Acceptance tests for cross-verified Logic Grid evaluation and hints."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.families.logic_grid.assistance import (
    ASSISTANCE_SCHEMA_VERSION,
    AssistanceError,
    HintLevel,
    HintResultStatus,
    LogicGridAssistanceContractDocument,
    LogicGridAssistanceService,
    LogicGridHintResult,
    MoveEvaluationStatus,
    default_logic_grid_assistance_service,
    opposite_atom,
)
from deductra.families.logic_grid.golden import harbor_morning
from deductra.families.logic_grid.play import (
    AssignCell,
    ClearCell,
    ExcludeCell,
    LogicGridPlaySession,
    PlayValidationMode,
    apply_logic_grid_play_action,
    start_logic_grid_play,
)
from deductra.families.logic_grid.schema import (
    logic_grid_assistance_json_schema,
    rendered_logic_grid_assistance_json_schema,
)
from deductra.families.logic_grid.specification import LogicGridSpec

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def puzzle() -> LogicGridSpec:
    return harbor_morning()


@pytest.fixture(scope="module")
def service() -> Iterator[LogicGridAssistanceService]:
    yield default_logic_grid_assistance_service()


def _continue_hint(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
    *,
    attempt_id: str,
) -> tuple[LogicGridPlaySession, LogicGridHintResult]:
    session = start_logic_grid_play(puzzle, attempt_id=attempt_id)
    result = service.request_hint(puzzle, session, level=HintLevel.CONTINUE)
    assert result.status is HintResultStatus.AVAILABLE
    assert result.hint is not None
    return session, result


def test_progressive_hint_ladder_limits_disclosure_and_preserves_evidence(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
) -> None:
    session = start_logic_grid_play(puzzle, attempt_id="deductra:attempt:assistance:ladder")
    results = tuple(service.request_hint(puzzle, session, level=level) for level in HintLevel)

    assert {item.status for item in results} == {HintResultStatus.AVAILABLE}
    hints = tuple(item.hint for item in results)
    assert all(item is not None for item in hints)
    evidence_hashes = {item.evidence.evidence_hash for item in hints if item is not None}
    assert len(evidence_hashes) == 1
    assert all(
        item.evidence.verification.decision.status.value == "cross_verified"
        for item in hints
        if item is not None
    )
    assert all(
        {certificate.backend_id for certificate in item.evidence.verification.decision.certificates}
        == {"z3", "cp-sat"}
        for item in hints
        if item is not None
    )

    reflection = results[HintLevel.REFLECTION].hint
    attention = results[HintLevel.ATTENTION].hint
    technique = results[HintLevel.TECHNIQUE].hint
    premises = results[HintLevel.PREMISES].hint
    deduction = results[HintLevel.DEDUCTION].hint
    explanation = results[HintLevel.EXPLANATION].hint
    continuation = results[HintLevel.CONTINUE].hint
    assert reflection is not None
    assert attention is not None
    assert technique is not None
    assert premises is not None
    assert deduction is not None
    assert explanation is not None
    assert continuation is not None

    assert reflection.disclosure.focus_variable_ids == ()
    assert reflection.disclosure.clue_ids == ()
    assert reflection.disclosure.rule_id is None
    assert reflection.disclosure.premises == ()
    assert reflection.disclosure.conclusion is None
    assert attention.disclosure.focus_variable_ids
    assert attention.disclosure.clue_ids
    assert attention.disclosure.rule_id is None
    assert technique.disclosure.rule_id == technique.evidence.rule.rule_id
    assert premises.disclosure.premises == premises.evidence.premises
    assert deduction.disclosure.conclusion is None
    assert explanation.disclosure.conclusion == explanation.evidence.conclusion
    assert continuation.disclosure.suggested_action is not None


def test_hint_identity_ignores_runtime_certificate_duration(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
) -> None:
    session = start_logic_grid_play(puzzle, attempt_id="deductra:attempt:assistance:stable")
    first = service.request_hint(puzzle, session, level=HintLevel.CONTINUE)
    second = service.request_hint(puzzle, session, level=HintLevel.CONTINUE)

    assert first.result_hash == second.result_hash
    assert first.hint is not None
    assert second.hint is not None
    assert first.hint.hint_hash == second.hint.hint_hash
    assert first.hint.evidence.evidence_hash == second.hint.evidence.evidence_hash


def test_move_evaluation_supports_a_verified_human_step(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
) -> None:
    session, hint_result = _continue_hint(
        service,
        puzzle,
        attempt_id="deductra:attempt:assistance:supported",
    )
    assert hint_result.hint is not None
    action = hint_result.hint.disclosure.suggested_action
    assert isinstance(action, (AssignCell, ExcludeCell))
    moved = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="deductra:event:assistance:supported",
        action=action,
    ).session

    evaluation = service.evaluate_move(
        puzzle,
        moved,
        source_event_id="deductra:event:assistance:supported",
    )

    assert evaluation.status is MoveEvaluationStatus.SUPPORTED
    assert evaluation.authoritative_atom == hint_result.hint.evidence.conclusion
    assert evaluation.verification is not None
    assert evaluation.technique is not None
    assert evaluation.technique.rule == hint_result.hint.evidence.rule
    assert evaluation.diagnostic_verifications == ()


def test_contradicted_move_blocks_progression_hint_with_verified_correction(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
) -> None:
    session, hint_result = _continue_hint(
        service,
        puzzle,
        attempt_id="deductra:attempt:assistance:contradicted",
    )
    assert hint_result.hint is not None
    conclusion = hint_result.hint.evidence.conclusion
    wrong = opposite_atom(conclusion)
    action = (
        AssignCell(variable_id=wrong.variable_id, value_id=wrong.value_id)
        if isinstance(wrong, AssignmentAtom)
        else ExcludeCell(variable_id=wrong.variable_id, value_id=wrong.value_id)
    )
    moved = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="deductra:event:assistance:contradicted",
        action=action,
    ).session

    evaluation = service.evaluate_move(
        puzzle,
        moved,
        source_event_id="deductra:event:assistance:contradicted",
    )
    blocked = service.request_hint(puzzle, moved, level=HintLevel.REFLECTION)

    assert evaluation.status is MoveEvaluationStatus.CONTRADICTED
    assert evaluation.authoritative_atom == conclusion
    assert evaluation.verification is not None
    assert blocked.status is HintResultStatus.CORRECTION_REQUIRED
    assert blocked.hint is None
    assert blocked.blocking_evaluation is not None
    assert blocked.blocking_evaluation.evaluation_hash == evaluation.evaluation_hash


def test_exam_mode_withholds_assistance_until_completion(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
) -> None:
    session = start_logic_grid_play(
        puzzle,
        attempt_id="deductra:attempt:assistance:exam",
        validation_mode=PlayValidationMode.EXAM,
    )
    result = service.request_hint(puzzle, session, level=HintLevel.REFLECTION)

    assert result.status is HintResultStatus.UNAVAILABLE_MODE
    assert result.code == "hints_withheld_in_exam"
    assert result.hint is None


def test_non_cell_and_unknown_events_are_not_evaluatable(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
) -> None:
    session = start_logic_grid_play(puzzle, attempt_id="deductra:attempt:assistance:error")
    given_variable_ids = {
        item.variable_id
        for item in puzzle.givens
        if isinstance(item, (AssignmentAtom, ExclusionAtom))
    }
    variable = next(item for item in puzzle.variables if item.variable_id not in given_variable_ids)
    anchor_category = next(
        item for item in puzzle.categories if item.category_id == puzzle.anchor_category_id
    )
    anchor_domain = next(
        item for item in puzzle.domains if item.domain_id == anchor_category.domain_id
    )
    cleared = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="deductra:event:assistance:clear",
        action=ClearCell(
            variable_id=variable.variable_id,
            value_id=anchor_domain.values[0].value_id,
        ),
    ).session

    with pytest.raises(AssistanceError, match="not an evaluatable"):
        service.evaluate_move(
            puzzle,
            cleared,
            source_event_id="deductra:event:assistance:clear",
        )
    with pytest.raises(AssistanceError, match="not retained"):
        service.evaluate_move(
            puzzle,
            cleared,
            source_event_id="deductra:event:assistance:missing",
        )


def test_assistance_contract_round_trips_and_rejects_hash_tampering(
    service: LogicGridAssistanceService,
    puzzle: LogicGridSpec,
) -> None:
    session = start_logic_grid_play(puzzle, attempt_id="deductra:attempt:assistance:schema")
    hint_result = service.request_hint(puzzle, session, level=HintLevel.EXPLANATION)
    document = LogicGridAssistanceContractDocument(hint_result=hint_result)

    encoded = document.model_dump_json()
    assert LogicGridAssistanceContractDocument.model_validate_json(encoded) == document
    assert document.schema_version == ASSISTANCE_SCHEMA_VERSION
    assert hint_result.hint is not None
    conclusion = hint_result.hint.evidence.conclusion
    action = (
        AssignCell(variable_id=conclusion.variable_id, value_id=conclusion.value_id)
        if isinstance(conclusion, AssignmentAtom)
        else ExcludeCell(variable_id=conclusion.variable_id, value_id=conclusion.value_id)
    )
    moved = apply_logic_grid_play_action(
        session,
        puzzle,
        event_id="deductra:event:assistance:schema",
        action=action,
    ).session
    evaluation = service.evaluate_move(
        puzzle,
        moved,
        source_event_id="deductra:event:assistance:schema",
    )
    with pytest.raises(ValidationError, match="exactly one"):
        LogicGridAssistanceContractDocument(
            hint_result=hint_result,
            move_evaluation=evaluation,
        )

    tampered = json.loads(hint_result.model_dump_json())
    tampered["message"] = "Altered"
    with pytest.raises(ValidationError, match="result_hash"):
        LogicGridHintResult.model_validate_json(json.dumps(tampered))


def test_assistance_schema_is_versioned_and_matches_checked_in_artifact() -> None:
    schema = logic_grid_assistance_json_schema()
    schema_path = REPOSITORY_ROOT / "schemas" / "logic-grid-assistance-v1.schema.json"

    assert schema["$id"] == "urn:deductra:schema:logic-grid-assistance:1"
    assert schema["properties"]["schema_version"]["const"] == ASSISTANCE_SCHEMA_VERSION
    assert schema_path.read_text(encoding="utf-8") == (rendered_logic_grid_assistance_json_schema())


def test_opposite_atom_is_involutive() -> None:
    assignment = AssignmentAtom(variable_id="deductra:variable:x", value_id="deductra:value:y")
    exclusion = ExclusionAtom(variable_id="deductra:variable:x", value_id="deductra:value:y")

    assert opposite_atom(assignment) == exclusion
    assert opposite_atom(exclusion) == assignment
    assert opposite_atom(opposite_atom(assignment)) == assignment
