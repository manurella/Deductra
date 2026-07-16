"""Immutable generator requests, evidence, decisions, and results."""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, cast

from pydantic import Field, field_serializer, field_validator, model_validator

from deductra.domain.base import DomainModel, freeze_json, thaw_json
from deductra.domain.ids import (
    CandidateId,
    GenerationRequestId,
    PuzzleId,
    RecipeId,
    RuleId,
)
from deductra.domain.puzzle import PuzzleSpec
from deductra.generation.events import GenerationEventType
from deductra.generation.lineage import GenerationLineage
from deductra.reasoning.events import Sha256Digest


class GenerationMode(StrEnum):
    """Operational mode requested without changing correctness gates."""

    INTERACTIVE = "interactive"
    BATCH_LIBRARY = "batch_library"
    GOLDEN_CANDIDATE = "golden_candidate"
    DIAGNOSTIC = "diagnostic"


class DifficultyLabel(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNRATED = "unrated"


class GenerationStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INTERNAL_FAILURE = "internal_failure"


class UniquenessStatus(StrEnum):
    NO_SOLUTION = "no_solution"
    UNIQUE = "unique"
    MULTIPLE = "multiple"
    UNKNOWN = "unknown"
    MODEL_INVALID = "model_invalid"
    BACKEND_DISAGREEMENT = "backend_disagreement"


class HumanSolveStatus(StrEnum):
    VERIFIED = "verified"
    STALLED = "stalled"
    INCONCLUSIVE = "inconclusive"


class NoveltyStatus(StrEnum):
    NOVEL = "novel"
    EXACT_DUPLICATE = "exact_duplicate"
    ISOMORPHIC_DUPLICATE = "isomorphic_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    INCONCLUSIVE = "inconclusive"


class RejectionReason(StrEnum):
    ZERO_SOLUTIONS = "zero_solutions"
    MULTIPLE_SOLUTIONS = "multiple_solutions"
    MODEL_INVALID = "model_invalid"
    HUMAN_SOLVER_STALLED = "human_solver_stalled"
    DIFFICULTY_MISMATCH = "difficulty_mismatch"
    REQUIRED_TECHNIQUE_MISSING = "required_technique_missing"
    FORBIDDEN_TECHNIQUE_USED = "forbidden_technique_used"
    EXACT_DUPLICATE = "exact_duplicate"
    ISOMORPHIC_DUPLICATE = "isomorphic_duplicate"
    NEAR_DUPLICATE = "near_duplicate"


class QuarantineReason(StrEnum):
    BACKEND_DISAGREEMENT = "backend_disagreement"
    UNIQUENESS_UNPROVEN = "uniqueness_unproven"
    HUMAN_SOLVE_INCONCLUSIVE = "human_solve_inconclusive"
    NOVELTY_INCONCLUSIVE = "novelty_inconclusive"
    EVIDENCE_INCOMPLETE = "evidence_incomplete"


class GenerationRequest(DomainModel):
    """Versioned, deterministic intent supplied to a family generator adapter."""

    request_id: GenerationRequestId
    family_id: str
    requested_difficulty: DifficultyLabel
    mode: GenerationMode
    seed: int
    generator_version: str
    recipe_id: RecipeId | None = None
    required_rule_ids: frozenset[RuleId] = frozenset()
    forbidden_rule_ids: frozenset[RuleId] = frozenset()
    size_profile: str
    novelty_policy_id: str
    style_profile_id: str | None = None
    time_budget_ms: Annotated[int, Field(gt=0)]
    max_candidates: Annotated[int, Field(gt=0)]

    @field_serializer("required_rule_ids", "forbidden_rule_ids")
    def serialize_rule_ids(self, value: frozenset[RuleId]) -> list[str]:
        """Keep request JSON independent of hash iteration order."""
        return sorted(value)

    @model_validator(mode="after")
    def validate_request(self) -> GenerationRequest:
        if self.requested_difficulty is DifficultyLabel.UNRATED:
            raise ValueError("generation requests require easy, medium, or hard difficulty")
        overlap = self.required_rule_ids & self.forbidden_rule_ids
        if overlap:
            raise ValueError(f"rules cannot be both required and forbidden: {sorted(overlap)}")
        return self


class UniquenessEvidence(DomainModel):
    """Backend-neutral result of enumerating at most two solutions."""

    status: UniquenessStatus
    solutions_found: Annotated[int, Field(ge=0, le=2)]
    backend_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_status(self) -> UniquenessEvidence:
        expected_counts = {
            UniquenessStatus.NO_SOLUTION: 0,
            UniquenessStatus.UNIQUE: 1,
            UniquenessStatus.MULTIPLE: 2,
        }
        expected = expected_counts.get(self.status)
        if expected is not None and self.solutions_found != expected:
            raise ValueError(f"{self.status.value} requires solutions_found={expected}")
        if self.status is UniquenessStatus.UNIQUE and (
            not self.backend_ids or not self.evidence_ids
        ):
            raise ValueError("unique status requires a backend and deterministic evidence")
        return self


class DifficultyEvidence(DomainModel):
    """Family-relative difficulty derived from a canonical human trace."""

    family_id: str
    catalogue_version: str
    label: DifficultyLabel
    score: float
    hardest_rule_rank: Annotated[int, Field(ge=0)]
    rule_histogram: Mapping[str, Annotated[int, Field(ge=0)]] = Field(default_factory=dict)
    total_human_steps: Annotated[int, Field(ge=0)]
    dependency_depth: Annotated[int, Field(ge=0)]
    mean_information_gain: float
    minimum_information_gain: float
    branch_pressure: Annotated[float, Field(ge=0)]
    contradiction_depth: Annotated[int, Field(ge=0)]
    working_memory_proxy: Annotated[float, Field(ge=0)]
    search_required: bool
    calibration_status: str
    trace_hash: Sha256Digest
    evidence_ids: tuple[str, ...]

    @field_validator("rule_histogram", mode="after")
    @classmethod
    def freeze_histogram(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        frozen = freeze_json(value)
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by field type
            raise TypeError("rule_histogram must be a mapping")
        return cast(Mapping[str, int], frozen)

    @field_serializer("rule_histogram")
    def serialize_histogram(self, value: Mapping[str, int]) -> dict[str, Any]:
        thawed = thaw_json(value)
        if not isinstance(thawed, dict):  # pragma: no cover - guaranteed by field type
            raise TypeError("rule_histogram must serialize as an object")
        return cast(dict[str, Any], thawed)

    @model_validator(mode="after")
    def validate_metrics(self) -> DifficultyEvidence:
        metrics = (
            self.score,
            self.mean_information_gain,
            self.minimum_information_gain,
            self.branch_pressure,
            self.working_memory_proxy,
        )
        if not all(math.isfinite(value) for value in metrics):
            raise ValueError("difficulty metrics must be finite")
        if self.total_human_steps != sum(self.rule_histogram.values()):
            raise ValueError("total_human_steps must equal the rule histogram total")
        return self


class PuzzleFingerprints(DomainModel):
    """Stable exact, equivalence, solution, structure, trace, and visual digests."""

    content_hash: Sha256Digest
    canonical_hash: Sha256Digest
    solution_hash: Sha256Digest
    structure_hash: Sha256Digest
    trace_signature: Sha256Digest
    visual_structure_hash: Sha256Digest


class NoveltyEvidence(DomainModel):
    """Conservative duplicate decision with closest-match evidence."""

    status: NoveltyStatus
    score: Annotated[float, Field(ge=0, le=1)]
    closest_puzzle_ids: tuple[PuzzleId, ...] = ()
    component_scores: Mapping[str, Annotated[float, Field(ge=0, le=1)]] = Field(
        default_factory=dict
    )
    evidence_ids: tuple[str, ...] = ()

    @field_validator("component_scores", mode="after")
    @classmethod
    def freeze_scores(cls, value: Mapping[str, float]) -> Mapping[str, float]:
        frozen = freeze_json(value)
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by field type
            raise TypeError("component_scores must be a mapping")
        return cast(Mapping[str, float], frozen)

    @field_serializer("component_scores")
    def serialize_scores(self, value: Mapping[str, float]) -> dict[str, Any]:
        thawed = thaw_json(value)
        if not isinstance(thawed, dict):  # pragma: no cover - guaranteed by field type
            raise TypeError("component_scores must serialize as an object")
        return cast(dict[str, Any], thawed)

    @model_validator(mode="after")
    def validate_novelty(self) -> NoveltyEvidence:
        if not math.isfinite(self.score) or not all(
            math.isfinite(value) for value in self.component_scores.values()
        ):
            raise ValueError("novelty scores must be finite")
        if (
            self.status
            in {
                NoveltyStatus.EXACT_DUPLICATE,
                NoveltyStatus.ISOMORPHIC_DUPLICATE,
                NoveltyStatus.NEAR_DUPLICATE,
            }
            and not self.closest_puzzle_ids
        ):
            raise ValueError("duplicate status requires a closest puzzle reference")
        return self


class GenerationVerification(DomainModel):
    """All deterministic evidence needed by the CR-007 acceptance gate."""

    uniqueness: UniquenessEvidence
    human_solve_status: HumanSolveStatus
    human_trace_hash: Sha256Digest | None
    difficulty: DifficultyEvidence | None
    fingerprints: PuzzleFingerprints | None
    novelty: NoveltyEvidence | None


class QuarantineRecord(DomainModel):
    """Fail-closed record for evidence that cannot authorize acceptance."""

    candidate_id: CandidateId
    reasons: tuple[QuarantineReason, ...]
    evidence_ids: tuple[str, ...] = ()
    retained_for_diagnostics: bool = True

    @model_validator(mode="after")
    def require_reason(self) -> QuarantineRecord:
        if not self.reasons:
            raise ValueError("quarantine requires at least one reason")
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("quarantine reasons must be unique")
        return self


class GenerationResult(DomainModel):
    """Terminal result whose puzzle is playable only when fully accepted."""

    request_id: GenerationRequestId
    candidate_id: CandidateId
    status: GenerationStatus
    puzzle: PuzzleSpec | None
    lineage: GenerationLineage
    verification: GenerationVerification | None
    rejection_reasons: tuple[RejectionReason, ...] = ()
    quarantine: QuarantineRecord | None = None

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> GenerationResult:
        if self.request_id != self.lineage.request_id:
            raise ValueError("result and lineage request identifiers must match")
        if self.candidate_id not in {
            candidate.candidate_id for candidate in self.lineage.candidates
        }:
            raise ValueError("result candidate must resolve within lineage")
        if self.status is GenerationStatus.ACCEPTED:
            if self.puzzle is None or self.verification is None:
                raise ValueError("accepted result requires a puzzle and verification")
            if self.rejection_reasons or self.quarantine:
                raise ValueError("accepted result cannot contain rejection or quarantine data")
            verification = self.verification
            if (
                verification.uniqueness.status is not UniquenessStatus.UNIQUE
                or verification.human_solve_status is not HumanSolveStatus.VERIFIED
                or verification.human_trace_hash is None
                or verification.difficulty is None
                or verification.difficulty.label is DifficultyLabel.UNRATED
                or verification.difficulty.search_required
                or not verification.difficulty.evidence_ids
                or verification.difficulty.trace_hash != verification.human_trace_hash
                or verification.fingerprints is None
                or verification.novelty is None
                or verification.novelty.status is not NoveltyStatus.NOVEL
                or not verification.novelty.evidence_ids
                or self.puzzle.identity.source_kind != "generated"
            ):
                raise ValueError("accepted result requires complete passing hard-gate evidence")
        elif self.puzzle is not None:
            raise ValueError("only accepted results may expose a playable puzzle")
        if self.status is GenerationStatus.REJECTED and not self.rejection_reasons:
            raise ValueError("rejected result requires at least one reason")
        if self.status is GenerationStatus.QUARANTINED:
            if self.quarantine is None or self.quarantine.candidate_id != self.candidate_id:
                raise ValueError("quarantined result requires a matching quarantine record")
        elif self.quarantine is not None:
            raise ValueError("quarantine data requires quarantined status")
        expected_terminal = {
            GenerationStatus.ACCEPTED: GenerationEventType.CANDIDATE_ACCEPTED,
            GenerationStatus.REJECTED: GenerationEventType.CANDIDATE_REJECTED,
            GenerationStatus.QUARANTINED: GenerationEventType.CANDIDATE_QUARANTINED,
        }.get(self.status)
        if expected_terminal is not None:
            terminal = self.lineage.events[-1]
            if (
                terminal.event_type is not expected_terminal
                or terminal.candidate_id != self.candidate_id
            ):
                raise ValueError("result status must match its terminal candidate lineage event")
        return self


class GenerationContractDocument(DomainModel):
    """Versioned schema root pairing one request with its terminal result."""

    request: GenerationRequest
    result: GenerationResult

    @model_validator(mode="after")
    def validate_pair(self) -> GenerationContractDocument:
        if self.request.request_id != self.result.request_id:
            raise ValueError("request and result identifiers must match")
        if self.result.status is GenerationStatus.ACCEPTED:
            puzzle = self.result.puzzle
            verification = self.result.verification
            candidate = next(
                (
                    item
                    for item in self.result.lineage.candidates
                    if item.candidate_id == self.result.candidate_id
                ),
                None,
            )
            if (
                puzzle is None
                or verification is None
                or verification.difficulty is None
                or self.result.lineage.generator_version != self.request.generator_version
                or candidate is None
                or candidate.seed != self.request.seed
                or (
                    self.request.recipe_id is not None
                    and candidate.recipe_id != self.request.recipe_id
                )
                or puzzle.identity.family_id != self.request.family_id
                or verification.difficulty.family_id != self.request.family_id
                or verification.difficulty.label is not self.request.requested_difficulty
                or not self.request.required_rule_ids.issubset(
                    verification.difficulty.rule_histogram
                )
                or bool(
                    self.request.forbidden_rule_ids & set(verification.difficulty.rule_histogram)
                )
            ):
                raise ValueError("accepted result does not satisfy its generation request")
        return self


def decide_generation_result(
    *,
    request: GenerationRequest,
    candidate_id: CandidateId,
    puzzle: PuzzleSpec,
    lineage: GenerationLineage,
    verification: GenerationVerification,
) -> GenerationResult:
    """Apply hard gates in order and fail closed on uncertain evidence."""
    quarantine_reasons: list[QuarantineReason] = []
    rejection_reasons: list[RejectionReason] = []

    candidate = next(
        (item for item in lineage.candidates if item.candidate_id == candidate_id),
        None,
    )
    if (
        lineage.request_id != request.request_id
        or lineage.generator_version != request.generator_version
        or candidate is None
        or candidate.seed != request.seed
        or (request.recipe_id is not None and candidate.recipe_id != request.recipe_id)
        or puzzle.identity.family_id != request.family_id
        or puzzle.identity.source_kind != "generated"
    ):
        rejection_reasons.append(RejectionReason.MODEL_INVALID)

    if verification.uniqueness.status is UniquenessStatus.BACKEND_DISAGREEMENT:
        quarantine_reasons.append(QuarantineReason.BACKEND_DISAGREEMENT)
    elif verification.uniqueness.status is UniquenessStatus.UNKNOWN:
        quarantine_reasons.append(QuarantineReason.UNIQUENESS_UNPROVEN)
    elif verification.uniqueness.status is UniquenessStatus.NO_SOLUTION:
        rejection_reasons.append(RejectionReason.ZERO_SOLUTIONS)
    elif verification.uniqueness.status is UniquenessStatus.MULTIPLE:
        rejection_reasons.append(RejectionReason.MULTIPLE_SOLUTIONS)
    elif verification.uniqueness.status is UniquenessStatus.MODEL_INVALID:
        rejection_reasons.append(RejectionReason.MODEL_INVALID)

    if verification.human_solve_status is HumanSolveStatus.INCONCLUSIVE:
        quarantine_reasons.append(QuarantineReason.HUMAN_SOLVE_INCONCLUSIVE)
    elif verification.human_solve_status is HumanSolveStatus.STALLED:
        rejection_reasons.append(RejectionReason.HUMAN_SOLVER_STALLED)

    if (
        verification.human_trace_hash is None
        or verification.difficulty is None
        or verification.fingerprints is None
        or verification.novelty is None
    ):
        quarantine_reasons.append(QuarantineReason.EVIDENCE_INCOMPLETE)
    else:
        if (
            verification.difficulty.label is not request.requested_difficulty
            or verification.difficulty.family_id != request.family_id
            or verification.difficulty.search_required
            or verification.difficulty.trace_hash != verification.human_trace_hash
        ):
            rejection_reasons.append(RejectionReason.DIFFICULTY_MISMATCH)
        used_rules = set(verification.difficulty.rule_histogram)
        if not request.required_rule_ids.issubset(used_rules):
            rejection_reasons.append(RejectionReason.REQUIRED_TECHNIQUE_MISSING)
        if request.forbidden_rule_ids & used_rules:
            rejection_reasons.append(RejectionReason.FORBIDDEN_TECHNIQUE_USED)
        novelty_rejections = {
            NoveltyStatus.EXACT_DUPLICATE: RejectionReason.EXACT_DUPLICATE,
            NoveltyStatus.ISOMORPHIC_DUPLICATE: RejectionReason.ISOMORPHIC_DUPLICATE,
            NoveltyStatus.NEAR_DUPLICATE: RejectionReason.NEAR_DUPLICATE,
        }
        if verification.novelty.status is NoveltyStatus.INCONCLUSIVE:
            quarantine_reasons.append(QuarantineReason.NOVELTY_INCONCLUSIVE)
        elif reason := novelty_rejections.get(verification.novelty.status):
            rejection_reasons.append(reason)

    if quarantine_reasons:
        evidence_ids = tuple(
            sorted(
                set(verification.uniqueness.evidence_ids)
                | set(verification.novelty.evidence_ids if verification.novelty else ())
            )
        )
        return GenerationResult(
            request_id=request.request_id,
            candidate_id=candidate_id,
            status=GenerationStatus.QUARANTINED,
            puzzle=None,
            lineage=lineage,
            verification=verification,
            quarantine=QuarantineRecord(
                candidate_id=candidate_id,
                reasons=tuple(dict.fromkeys(quarantine_reasons)),
                evidence_ids=evidence_ids,
            ),
        )
    if rejection_reasons:
        return GenerationResult(
            request_id=request.request_id,
            candidate_id=candidate_id,
            status=GenerationStatus.REJECTED,
            puzzle=None,
            lineage=lineage,
            verification=verification,
            rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
        )
    return GenerationResult(
        request_id=request.request_id,
        candidate_id=candidate_id,
        status=GenerationStatus.ACCEPTED,
        puzzle=puzzle,
        lineage=lineage,
        verification=verification,
    )
