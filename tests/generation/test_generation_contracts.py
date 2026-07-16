"""CR-007 property and round-trip tests for generator-foundation contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from deductra.domain.constraints import AllDifferentConstraint
from deductra.domain.puzzle import DisplaySpec, ProvenanceBundle, PuzzleIdentity, PuzzleSpec
from deductra.domain.serialization import canonical_json
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.generation import (
    GENESIS_EVENT_HASH,
    CandidateLineage,
    DifficultyEvaluator,
    DifficultyEvidence,
    DifficultyLabel,
    FingerprintEvaluator,
    GenerationContractDocument,
    GenerationEventType,
    GenerationLineage,
    GenerationMode,
    GenerationRequest,
    GenerationStatus,
    GenerationVerification,
    HumanSolveStatus,
    NoveltyEvaluator,
    NoveltyEvidence,
    NoveltyStatus,
    PuzzleFingerprints,
    QuarantineReason,
    RejectionReason,
    UniquenessEvaluator,
    UniquenessEvidence,
    UniquenessStatus,
    decide_generation_result,
    generation_event_chain_failures,
    seal_generation_event,
)
from deductra.generation.schema import rendered_generation_contract_json_schema

NOW = datetime(2026, 7, 16, 15, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]
REQUEST_ID = "deductra:generation-request:test"
GENERATION_ID = "deductra:generation:test"
CANDIDATE_ID = "deductra:candidate:test"
TRACE_HASH = "a" * 64


def request(*, seed: int = 42) -> GenerationRequest:
    return GenerationRequest(
        request_id=REQUEST_ID,
        family_id="contract-test",
        requested_difficulty=DifficultyLabel.EASY,
        mode=GenerationMode.DIAGNOSTIC,
        seed=seed,
        generator_version="1.0.0",
        recipe_id="deductra:recipe:test",
        required_rule_ids=frozenset({"deductra:rule:b", "deductra:rule:a"}),
        forbidden_rule_ids=frozenset({"deductra:rule:z"}),
        size_profile="tiny",
        novelty_policy_id="strict-v1",
        time_budget_ms=1_000,
        max_candidates=5,
    )


def puzzle() -> PuzzleSpec:
    x = "deductra:variable:x"
    y = "deductra:variable:y"
    domain_id = "deductra:domain:letters"
    values = (
        DomainValue(value_id="deductra:value:a", label="A"),
        DomainValue(value_id="deductra:value:b", label="B"),
    )
    return PuzzleSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:generated-test",
            revision_id="deductra:revision:generated-test:1",
            family_id="contract-test",
            schema_version="1.0.0",
            title="Generated contract test",
            source_kind="generated",
            created_at=NOW,
        ),
        domains=(
            Domain(
                domain_id=domain_id,
                values=values,
                ordered=False,
                distinct_by_default=True,
            ),
        ),
        variables=(
            Variable(variable_id=x, label="X", domain_id=domain_id, role="answer"),
            Variable(variable_id=y, label="Y", domain_id=domain_id, role="answer"),
        ),
        constraints=(
            AllDifferentConstraint(
                constraint_id="deductra:constraint:different",
                label="Values differ",
                variable_ids=(x, y),
            ),
        ),
        clues=(),
        givens=(),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def lineage(*, terminal: GenerationEventType = GenerationEventType.CANDIDATE_ACCEPTED):
    requested = seal_generation_event(
        event_id="deductra:generation-event:requested",
        generation_id=GENERATION_ID,
        request_id=REQUEST_ID,
        sequence_no=0,
        event_type=GenerationEventType.GENERATION_REQUESTED,
        schema_version="1.0.0",
        occurred_at=NOW,
        previous_event_hash=GENESIS_EVENT_HASH,
        details={"seed": 42},
    )
    assembled = seal_generation_event(
        event_id="deductra:generation-event:assembled",
        generation_id=GENERATION_ID,
        request_id=REQUEST_ID,
        sequence_no=1,
        event_type=GenerationEventType.CANDIDATE_ASSEMBLED,
        schema_version="1.0.0",
        occurred_at=NOW,
        previous_event_hash=requested.event_hash,
        candidate_id=CANDIDATE_ID,
    )
    finished = seal_generation_event(
        event_id="deductra:generation-event:finished",
        generation_id=GENERATION_ID,
        request_id=REQUEST_ID,
        sequence_no=2,
        event_type=terminal,
        schema_version="1.0.0",
        occurred_at=NOW,
        previous_event_hash=assembled.event_hash,
        candidate_id=CANDIDATE_ID,
    )
    return GenerationLineage(
        generation_id=GENERATION_ID,
        request_id=REQUEST_ID,
        generator_version="1.0.0",
        rng_provider="python-random",
        rng_version="3.13",
        dependency_versions=(("deductra", "0.0.0"),),
        candidates=(
            CandidateLineage(
                candidate_id=CANDIDATE_ID,
                parent_candidate_id=None,
                recipe_id="deductra:recipe:test",
                recipe_version="1.0.0",
                seed=42,
                operation_parameters={"size": 2},
                created_event_id=assembled.event_id,
            ),
        ),
        events=(requested, assembled, finished),
    )


def fingerprints() -> PuzzleFingerprints:
    return PuzzleFingerprints(
        content_hash="1" * 64,
        canonical_hash="2" * 64,
        solution_hash="3" * 64,
        structure_hash="4" * 64,
        trace_signature="5" * 64,
        visual_structure_hash="6" * 64,
    )


def verification(
    *,
    uniqueness: UniquenessStatus = UniquenessStatus.UNIQUE,
    novelty: NoveltyStatus = NoveltyStatus.NOVEL,
) -> GenerationVerification:
    solutions_found = {
        UniquenessStatus.NO_SOLUTION: 0,
        UniquenessStatus.UNIQUE: 1,
        UniquenessStatus.MULTIPLE: 2,
    }.get(uniqueness, 1)
    return GenerationVerification(
        uniqueness=UniquenessEvidence(
            status=uniqueness,
            solutions_found=solutions_found,
            backend_ids=("solver-a", "solver-b"),
            evidence_ids=("deductra:evidence:uniqueness",),
        ),
        human_solve_status=HumanSolveStatus.VERIFIED,
        human_trace_hash=TRACE_HASH,
        difficulty=DifficultyEvidence(
            family_id="contract-test",
            catalogue_version="1.0.0",
            label=DifficultyLabel.EASY,
            score=0.2,
            hardest_rule_rank=1,
            rule_histogram={"deductra:rule:a": 1, "deductra:rule:b": 1},
            total_human_steps=2,
            dependency_depth=1,
            mean_information_gain=0.5,
            minimum_information_gain=0.25,
            branch_pressure=0.0,
            contradiction_depth=0,
            working_memory_proxy=1.0,
            search_required=False,
            calibration_status="theoretical",
            trace_hash=TRACE_HASH,
            evidence_ids=("deductra:evidence:difficulty",),
        ),
        fingerprints=fingerprints(),
        novelty=NoveltyEvidence(
            status=novelty,
            score=1.0 if novelty is NoveltyStatus.NOVEL else 0.0,
            closest_puzzle_ids=(
                ()
                if novelty in {NoveltyStatus.NOVEL, NoveltyStatus.INCONCLUSIVE}
                else ("deductra:puzzle:existing",)
            ),
            component_scores={"structure": 0.0},
            evidence_ids=("deductra:evidence:novelty",),
        ),
    )


@pytest.mark.parametrize("seed", [-1, 0, 1, 2**31 - 1])
def test_request_round_trip_is_canonical_for_representative_seeds(seed: int) -> None:
    original = request(seed=seed)
    encoded = canonical_json(original)
    restored = GenerationRequest.model_validate_json(encoded)
    assert restored == original
    assert canonical_json(restored) == encoded
    assert encoded.index("deductra:rule:a") < encoded.index("deductra:rule:b")


def test_accepted_result_round_trips_with_complete_artifact_and_evidence() -> None:
    result = decide_generation_result(
        request=request(),
        candidate_id=CANDIDATE_ID,
        puzzle=puzzle(),
        lineage=lineage(),
        verification=verification(),
    )
    document = GenerationContractDocument(request=request(), result=result)
    restored = GenerationContractDocument.model_validate_json(canonical_json(document))
    assert restored == document
    assert restored.result.status is GenerationStatus.ACCEPTED
    assert restored.result.puzzle == puzzle()


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (UniquenessStatus.UNKNOWN, QuarantineReason.UNIQUENESS_UNPROVEN),
        (UniquenessStatus.BACKEND_DISAGREEMENT, QuarantineReason.BACKEND_DISAGREEMENT),
    ],
)
def test_uncertain_uniqueness_is_quarantined(
    status: UniquenessStatus, reason: QuarantineReason
) -> None:
    result = decide_generation_result(
        request=request(),
        candidate_id=CANDIDATE_ID,
        puzzle=puzzle(),
        lineage=lineage(terminal=GenerationEventType.CANDIDATE_QUARANTINED),
        verification=verification(uniqueness=status),
    )
    assert result.status is GenerationStatus.QUARANTINED
    assert result.puzzle is None
    assert result.quarantine is not None
    assert reason in result.quarantine.reasons


def test_accepted_contract_cannot_bypass_the_hard_gate() -> None:
    accepted = decide_generation_result(
        request=request(),
        candidate_id=CANDIDATE_ID,
        puzzle=puzzle(),
        lineage=lineage(),
        verification=verification(),
    )
    with pytest.raises(ValidationError, match="passing hard-gate evidence"):
        accepted.__class__(
            **accepted.model_dump(exclude={"verification"}),
            verification=verification(uniqueness=UniquenessStatus.UNKNOWN),
        )


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (NoveltyStatus.EXACT_DUPLICATE, RejectionReason.EXACT_DUPLICATE),
        (NoveltyStatus.ISOMORPHIC_DUPLICATE, RejectionReason.ISOMORPHIC_DUPLICATE),
        (NoveltyStatus.NEAR_DUPLICATE, RejectionReason.NEAR_DUPLICATE),
    ],
)
def test_known_duplicates_are_rejected(status: NoveltyStatus, reason: RejectionReason) -> None:
    result = decide_generation_result(
        request=request(),
        candidate_id=CANDIDATE_ID,
        puzzle=puzzle(),
        lineage=lineage(terminal=GenerationEventType.CANDIDATE_REJECTED),
        verification=verification(novelty=status),
    )
    assert result.status is GenerationStatus.REJECTED
    assert result.puzzle is None
    assert reason in result.rejection_reasons


def test_lineage_detects_tampering_without_mutating_the_source() -> None:
    source = lineage()
    tampered = source.events[1].model_copy(update={"details": {"changed": True}})
    assert generation_event_chain_failures((source.events[0], tampered, source.events[2])) == (
        "deductra:generation-event:assembled:event_hash",
    )
    assert generation_event_chain_failures(source.events) == ()


def test_generation_request_rejects_overlapping_rule_policy() -> None:
    original = request()
    payload = original.model_dump(exclude={"required_rule_ids", "forbidden_rule_ids"})
    with pytest.raises(ValidationError, match="both required and forbidden"):
        GenerationRequest(
            **payload,
            required_rule_ids=frozenset({"deductra:rule:a"}),
            forbidden_rule_ids=frozenset({"deductra:rule:a"}),
        )


def test_evidence_ports_are_structural_and_do_not_supply_implementations() -> None:
    class EmptyAdapter:
        pass

    adapter = EmptyAdapter()
    assert not isinstance(adapter, UniquenessEvaluator)
    assert not isinstance(adapter, DifficultyEvaluator)
    assert not isinstance(adapter, FingerprintEvaluator)
    assert not isinstance(adapter, NoveltyEvaluator)


def test_checked_in_generation_contract_schema_is_current() -> None:
    path = ROOT / "schemas" / "generation-contract-v1.schema.json"
    assert path.read_text(encoding="utf-8") == rendered_generation_contract_json_schema()
