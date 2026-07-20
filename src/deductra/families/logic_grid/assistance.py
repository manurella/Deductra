"""Cross-verified Logic Grid move evaluation and progressive hint disclosure."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Literal, Self

from pydantic import model_validator

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.base import DomainModel
from deductra.domain.ids import (
    AttemptId,
    ClueId,
    ConstraintId,
    EventId,
    PuzzleRevisionId,
    RuleCandidateId,
    RuleId,
    VariableId,
)
from deductra.domain.serialization import canonical_json, canonical_sha256
from deductra.families.logic_grid.play import (
    AssignCell,
    ExcludeCell,
    LogicGridPlaySession,
    PlayAction,
    PlayEvent,
    PlaySessionStatus,
    PlayValidationMode,
)
from deductra.families.logic_grid.solver import logic_grid_rules
from deductra.families.logic_grid.specification import LogicGridSpec
from deductra.reasoning.events import Sha256Digest
from deductra.reasoning.policy import ReasoningPolicy, select_rule_application
from deductra.reasoning.rules import (
    ProposedDeduction,
    RuleApplicationCandidate,
    RuleReference,
    discover_rule_applications,
)
from deductra.reasoning.state import PuzzleState, build_state, create_initial_state
from deductra.verification.contracts import (
    AssignmentNegation,
    EliminationNegation,
    ProofObligation,
    VerificationRecord,
    VerificationStatus,
)
from deductra.verification.coordinator import CrossVerificationCoordinator
from deductra.verification.cpsat_backend import CpSatProofBackend
from deductra.verification.z3_backend import Z3ProofBackend

ASSISTANCE_SCHEMA_VERSION = "1.0.0"
type EvaluatableAtom = AssignmentAtom | ExclusionAtom


class MoveEvaluationStatus(StrEnum):
    """Cross-verification outcome for one accepted tentative cell move."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    QUARANTINED = "quarantined"


class HintLevel(IntEnum):
    """Progressive disclosure level requested by the player."""

    REFLECTION = 0
    ATTENTION = 1
    TECHNIQUE = 2
    PREMISES = 3
    DEDUCTION = 4
    EXPLANATION = 5
    CONTINUE = 6


class HintKind(StrEnum):
    """Purpose served by one available hint."""

    PROGRESSION = "progression"


class HintResultStatus(StrEnum):
    """Stable outcome of requesting assistance from one session state."""

    AVAILABLE = "available"
    CORRECTION_REQUIRED = "correction_required"
    ALREADY_COMPLETE = "already_complete"
    UNAVAILABLE_MODE = "unavailable_mode"
    HUMAN_RULES_EXHAUSTED = "human_rules_exhausted"
    INCONCLUSIVE = "inconclusive"
    QUARANTINED = "quarantined"


class LogicGridClueEvidence(DomainModel):
    """One presentation clue supporting a verified human-rule candidate."""

    clue_id: ClueId
    text: str
    constraint_ids: tuple[ConstraintId, ...]

    @model_validator(mode="after")
    def validate_clue_evidence(self) -> Self:
        if not self.text.strip() or not self.constraint_ids:
            raise ValueError("clue evidence requires text and a supporting constraint")
        if self.constraint_ids != tuple(sorted(set(self.constraint_ids))):
            raise ValueError("clue evidence constraints must be unique and sorted")
        return self


class LogicGridTechniqueEvidence(DomainModel):
    """Auditable human-rule explanation for one cross-verified atom."""

    source_state_hash: Sha256Digest
    candidate_id: RuleCandidateId
    rule: RuleReference
    premises: tuple[Atom, ...]
    conclusion: EvaluatableAtom
    affected_variable_ids: tuple[VariableId, ...]
    supporting_constraint_ids: tuple[ConstraintId, ...]
    clues: tuple[LogicGridClueEvidence, ...]
    proposal_hash: Sha256Digest
    verification: VerificationRecord
    evidence_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.verification.obligation.source_state_hash != self.source_state_hash:
            raise ValueError("technique verification must bind the disclosed source state")
        if self.verification.obligation.claimed_conclusions != (self.conclusion,):
            raise ValueError("technique verification must prove the disclosed conclusion")
        if self.verification.decision.status is not VerificationStatus.CROSS_VERIFIED:
            raise ValueError("hint technique evidence requires independent cross-verification")
        if self.premises != self.verification.obligation.assumptions:
            raise ValueError("technique premises must equal proof assumptions")
        if not self.affected_variable_ids:
            raise ValueError("technique evidence requires an affected variable")
        if self.affected_variable_ids != tuple(sorted(set(self.affected_variable_ids))):
            raise ValueError("affected variables must be unique and sorted")
        if self.supporting_constraint_ids != tuple(sorted(set(self.supporting_constraint_ids))):
            raise ValueError("supporting constraints must be unique and sorted")
        clue_constraints = {
            constraint_id for clue in self.clues for constraint_id in clue.constraint_ids
        }
        if not clue_constraints <= set(self.supporting_constraint_ids):
            raise ValueError("clue evidence must resolve supporting constraints")
        if self.evidence_hash != compute_technique_evidence_hash(self):
            raise ValueError("evidence_hash does not match technique evidence")
        return self


class LogicGridMoveEvaluation(DomainModel):
    """Cross-verified classification of one retained tentative cell event."""

    schema_version: Literal["1.0.0"] = ASSISTANCE_SCHEMA_VERSION
    attempt_id: AttemptId
    puzzle_revision_id: PuzzleRevisionId
    source_session_hash: Sha256Digest
    source_event_id: EventId
    submitted_atom: EvaluatableAtom
    status: MoveEvaluationStatus
    authoritative_atom: EvaluatableAtom | None = None
    verification: VerificationRecord | None = None
    technique: LogicGridTechniqueEvidence | None = None
    diagnostic_verifications: tuple[VerificationRecord, ...] = ()
    evaluation_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        decided = self.status in {
            MoveEvaluationStatus.SUPPORTED,
            MoveEvaluationStatus.CONTRADICTED,
        }
        if decided != (self.authoritative_atom is not None and self.verification is not None):
            raise ValueError("decided evaluations require one authoritative verified atom")
        if self.status is MoveEvaluationStatus.SUPPORTED and (
            self.authoritative_atom != self.submitted_atom
        ):
            raise ValueError("supported evaluations must authorize the submitted atom")
        if self.status is MoveEvaluationStatus.CONTRADICTED and (
            self.authoritative_atom != opposite_atom(self.submitted_atom)
        ):
            raise ValueError("contradicted evaluations must authorize the opposite atom")
        if self.verification is not None:
            if self.verification.decision.status is not VerificationStatus.CROSS_VERIFIED:
                raise ValueError("move authority requires independent cross-verification")
            if self.verification.obligation.claimed_conclusions != (self.authoritative_atom,):
                raise ValueError("move verification must prove the authoritative atom")
        if self.technique is not None and self.technique.conclusion != self.authoritative_atom:
            raise ValueError("technique evidence must explain the authoritative atom")
        if decided and self.diagnostic_verifications:
            raise ValueError("decided evaluations do not retain inconclusive diagnostics")
        if not decided and len(self.diagnostic_verifications) != 2:
            raise ValueError("undecided evaluations require claim and opposite diagnostics")
        if self.evaluation_hash != compute_move_evaluation_hash(self):
            raise ValueError("evaluation_hash does not match the move evaluation")
        return self


class LogicGridHintDisclosure(DomainModel):
    """The only level-sensitive content a presentation adapter may reveal."""

    level: HintLevel
    message: str
    focus_variable_ids: tuple[VariableId, ...] = ()
    clue_ids: tuple[ClueId, ...] = ()
    rule_id: RuleId | None = None
    premises: tuple[Atom, ...] = ()
    conclusion: EvaluatableAtom | None = None
    suggested_action: PlayAction | None = None

    @model_validator(mode="after")
    def validate_disclosure_ladder(self) -> Self:
        if not self.message.strip():
            raise ValueError("hint disclosure requires a presentation-safe message")
        if self.focus_variable_ids != tuple(sorted(set(self.focus_variable_ids))):
            raise ValueError("hint focus variables must be unique and sorted")
        if self.clue_ids != tuple(sorted(set(self.clue_ids))):
            raise ValueError("hint clue identifiers must be unique and sorted")
        if self.level < HintLevel.ATTENTION and (self.focus_variable_ids or self.clue_ids):
            raise ValueError("reflection hints cannot disclose a target")
        if self.level < HintLevel.TECHNIQUE and self.rule_id is not None:
            raise ValueError("the applicable technique is disclosed only from level 2")
        if self.level < HintLevel.PREMISES and self.premises:
            raise ValueError("premises are disclosed only from level 3")
        if self.level < HintLevel.EXPLANATION and self.conclusion is not None:
            raise ValueError("the conclusion is disclosed only from level 5")
        if self.level < HintLevel.CONTINUE and self.suggested_action is not None:
            raise ValueError("an applicable action is disclosed only at level 6")
        if self.level >= HintLevel.ATTENTION and not self.focus_variable_ids:
            raise ValueError("attention-level hints require a focus target")
        if self.level >= HintLevel.TECHNIQUE and self.rule_id is None:
            raise ValueError("technique-level hints require a rule identity")
        if self.level >= HintLevel.EXPLANATION and self.conclusion is None:
            raise ValueError("explanation-level hints require the verified conclusion")
        if self.level is HintLevel.CONTINUE and self.suggested_action is None:
            raise ValueError("continue-level hints require an explicit play action")
        return self


class LogicGridHint(DomainModel):
    """One evidence-backed hint with an auditable core and bounded disclosure."""

    schema_version: Literal["1.0.0"] = ASSISTANCE_SCHEMA_VERSION
    attempt_id: AttemptId
    puzzle_revision_id: PuzzleRevisionId
    source_session_hash: Sha256Digest
    kind: HintKind
    evidence: LogicGridTechniqueEvidence
    disclosure: LogicGridHintDisclosure
    hint_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_hint(self) -> Self:
        if self.disclosure.level >= HintLevel.ATTENTION and (
            not set(self.disclosure.focus_variable_ids) <= set(self.evidence.affected_variable_ids)
        ):
            raise ValueError("hint focus must resolve to the verified candidate")
        if self.disclosure.level >= HintLevel.TECHNIQUE and (
            self.disclosure.rule_id != self.evidence.rule.rule_id
        ):
            raise ValueError("disclosed rule must match verified evidence")
        if self.disclosure.level >= HintLevel.PREMISES and (
            self.disclosure.premises != self.evidence.premises
        ):
            raise ValueError("disclosed premises must match verified evidence")
        if self.disclosure.level >= HintLevel.EXPLANATION and (
            self.disclosure.conclusion != self.evidence.conclusion
        ):
            raise ValueError("disclosed conclusion must match verified evidence")
        if self.hint_hash != compute_hint_hash(self):
            raise ValueError("hint_hash does not match the evidence-backed hint")
        return self


class LogicGridHintResult(DomainModel):
    """Stable available or unavailable outcome for one hint request."""

    schema_version: Literal["1.0.0"] = ASSISTANCE_SCHEMA_VERSION
    attempt_id: AttemptId
    puzzle_revision_id: PuzzleRevisionId
    source_session_hash: Sha256Digest
    status: HintResultStatus
    code: str
    message: str
    hint: LogicGridHint | None = None
    blocking_evaluation: LogicGridMoveEvaluation | None = None
    result_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if not self.code or not self.message:
            raise ValueError("hint results require stable code and message")
        if (self.status is HintResultStatus.AVAILABLE) != (self.hint is not None):
            raise ValueError("only available hint results may carry a hint")
        if (self.status is HintResultStatus.CORRECTION_REQUIRED) != (
            self.blocking_evaluation is not None
        ):
            raise ValueError("correction-required results need one blocking evaluation")
        if self.hint is not None and self.hint.source_session_hash != self.source_session_hash:
            raise ValueError("hint result and hint must bind the same session")
        if (
            self.blocking_evaluation is not None
            and self.blocking_evaluation.source_session_hash != self.source_session_hash
        ):
            raise ValueError("blocking evaluation must bind the requested session")
        if self.result_hash != compute_hint_result_hash(self):
            raise ValueError("result_hash does not match the hint result")
        return self


class LogicGridAssistanceContractDocument(DomainModel):
    """Serialized major-v1 envelope for exactly one assistance result."""

    schema_version: Literal["1.0.0"] = ASSISTANCE_SCHEMA_VERSION
    move_evaluation: LogicGridMoveEvaluation | None = None
    hint_result: LogicGridHintResult | None = None

    @model_validator(mode="after")
    def require_one_result(self) -> Self:
        if (self.move_evaluation is None) == (self.hint_result is None):
            raise ValueError("an assistance document requires exactly one result")
        return self


class AssistanceError(ValueError):
    """A caller requested assistance for an invalid or non-evaluatable source."""


def compute_technique_evidence_hash(evidence: LogicGridTechniqueEvidence) -> str:
    return canonical_sha256(
        {
            "source_state_hash": evidence.source_state_hash,
            "candidate_id": evidence.candidate_id,
            "rule": evidence.rule,
            "premises": evidence.premises,
            "conclusion": evidence.conclusion,
            "affected_variable_ids": evidence.affected_variable_ids,
            "supporting_constraint_ids": evidence.supporting_constraint_ids,
            "clues": evidence.clues,
            "proposal_hash": evidence.proposal_hash,
            "verification": _verification_fingerprint(evidence.verification),
        }
    )


def compute_move_evaluation_hash(evaluation: LogicGridMoveEvaluation) -> str:
    return canonical_sha256(
        {
            "schema_version": evaluation.schema_version,
            "attempt_id": evaluation.attempt_id,
            "puzzle_revision_id": evaluation.puzzle_revision_id,
            "source_session_hash": evaluation.source_session_hash,
            "source_event_id": evaluation.source_event_id,
            "submitted_atom": evaluation.submitted_atom,
            "status": evaluation.status,
            "authoritative_atom": evaluation.authoritative_atom,
            "verification": (
                _verification_fingerprint(evaluation.verification)
                if evaluation.verification is not None
                else None
            ),
            "technique_evidence_hash": (
                evaluation.technique.evidence_hash if evaluation.technique is not None else None
            ),
            "diagnostic_verifications": tuple(
                _verification_fingerprint(item) for item in evaluation.diagnostic_verifications
            ),
        }
    )


def compute_hint_hash(hint: LogicGridHint) -> str:
    return canonical_sha256(
        {
            "schema_version": hint.schema_version,
            "attempt_id": hint.attempt_id,
            "puzzle_revision_id": hint.puzzle_revision_id,
            "source_session_hash": hint.source_session_hash,
            "kind": hint.kind,
            "evidence_hash": hint.evidence.evidence_hash,
            "disclosure": hint.disclosure,
        }
    )


def compute_hint_result_hash(result: LogicGridHintResult) -> str:
    return canonical_sha256(
        {
            "schema_version": result.schema_version,
            "attempt_id": result.attempt_id,
            "puzzle_revision_id": result.puzzle_revision_id,
            "source_session_hash": result.source_session_hash,
            "status": result.status,
            "code": result.code,
            "message": result.message,
            "hint_hash": result.hint.hint_hash if result.hint is not None else None,
            "blocking_evaluation_hash": (
                result.blocking_evaluation.evaluation_hash
                if result.blocking_evaluation is not None
                else None
            ),
        }
    )


def _verification_fingerprint(record: VerificationRecord) -> dict[str, object]:
    """Exclude runtime duration and self-hashes from stable assistance identity."""
    return {
        "obligation": record.obligation,
        "status": record.decision.status,
        "reason": record.decision.reason,
        "certificates": tuple(
            {
                "certificate_id": item.certificate_id,
                "backend_id": item.backend_id,
                "backend_version": item.backend_version,
                "encoding_version": item.encoding_version,
                "obligation_id": item.obligation_id,
                "result": item.result,
                "unsat_core_refs": item.unsat_core_refs,
                "model_snapshot": item.model_snapshot,
                "raw_artifact_hash": item.raw_artifact_hash,
            }
            for item in record.decision.certificates
        ),
    }


def opposite_atom(atom: EvaluatableAtom) -> EvaluatableAtom:
    """Return the exact logical opposite of one assignment or exclusion."""
    if isinstance(atom, AssignmentAtom):
        return ExclusionAtom(variable_id=atom.variable_id, value_id=atom.value_id)
    return AssignmentAtom(variable_id=atom.variable_id, value_id=atom.value_id)


def _initial_state(puzzle: LogicGridSpec, *, purpose: str) -> PuzzleState:
    digest = canonical_sha256(
        {"puzzle_revision_id": puzzle.identity.revision_id, "purpose": purpose}
    )
    return create_initial_state(
        puzzle,
        state_id=f"deductra:state:logic-grid-assistance:{digest}",
        branch_id=f"deductra:branch:logic-grid-assistance:{digest}",
        sequence_no=0,
    )


def _proof_record(
    puzzle: LogicGridSpec,
    state: PuzzleState,
    atom: EvaluatableAtom,
    coordinator: CrossVerificationCoordinator,
    *,
    purpose: str,
    assumptions: tuple[Atom, ...] = (),
    timeout_ms: int,
) -> VerificationRecord:
    digest = canonical_sha256(
        {
            "assumptions": assumptions,
            "atom": atom,
            "purpose": purpose,
            "puzzle_revision_id": puzzle.identity.revision_id,
            "source_state_hash": state.state_hash,
        }
    )
    negated = (
        AssignmentNegation(variable_id=atom.variable_id, value_id=atom.value_id)
        if isinstance(atom, AssignmentAtom)
        else EliminationNegation(variable_id=atom.variable_id, value_id=atom.value_id)
    )
    obligation = ProofObligation(
        obligation_id=f"deductra:obligation:logic-grid-assistance:{digest}",
        puzzle_revision_id=puzzle.identity.revision_id,
        source_state_hash=state.state_hash,
        assumptions=assumptions,
        claimed_conclusions=(atom,),
        negated_claim=negated,
    )
    return VerificationRecord(
        obligation=obligation,
        decision=coordinator.verify(puzzle, state, obligation, timeout_ms=timeout_ms),
    )


def _is_cross_verified(record: VerificationRecord) -> bool:
    return record.decision.status is VerificationStatus.CROSS_VERIFIED


def _clue_evidence(
    puzzle: LogicGridSpec, supporting_constraints: tuple[ConstraintId, ...]
) -> tuple[LogicGridClueEvidence, ...]:
    supporting = set(supporting_constraints)
    return tuple(
        LogicGridClueEvidence(
            clue_id=clue.clue_id,
            text=clue.text,
            constraint_ids=tuple(sorted(set(clue.constraint_ids) & supporting)),
        )
        for clue in sorted(puzzle.clues, key=lambda item: item.clue_id)
        if set(clue.constraint_ids) & supporting
    )


def _seal_technique_evidence(
    puzzle: LogicGridSpec,
    candidate: RuleApplicationCandidate,
    proposal: ProposedDeduction,
    verification: VerificationRecord,
) -> LogicGridTechniqueEvidence:
    conclusion = proposal.conclusions[0]
    if not isinstance(conclusion, (AssignmentAtom, ExclusionAtom)):
        raise AssistanceError("Logic Grid assistance supports cell conclusions only")
    affected_variable_ids = tuple(sorted(candidate.affected_variables))
    supporting_constraint_ids = tuple(sorted(proposal.supporting_constraints))
    clues = _clue_evidence(puzzle, proposal.supporting_constraints)
    proposal_hash = canonical_sha256(proposal)
    unsigned = LogicGridTechniqueEvidence.model_construct(
        source_state_hash=proposal.source_state_hash,
        candidate_id=proposal.candidate_id,
        rule=proposal.rule,
        premises=proposal.premises,
        conclusion=conclusion,
        affected_variable_ids=affected_variable_ids,
        supporting_constraint_ids=supporting_constraint_ids,
        clues=clues,
        proposal_hash=proposal_hash,
        verification=verification,
        evidence_hash="0" * 64,
    )
    return LogicGridTechniqueEvidence(
        source_state_hash=proposal.source_state_hash,
        candidate_id=proposal.candidate_id,
        rule=proposal.rule,
        premises=proposal.premises,
        conclusion=conclusion,
        affected_variable_ids=affected_variable_ids,
        supporting_constraint_ids=supporting_constraint_ids,
        clues=clues,
        proposal_hash=proposal_hash,
        verification=verification,
        evidence_hash=compute_technique_evidence_hash(unsigned),
    )


def _event_atom(event: PlayEvent) -> EvaluatableAtom:
    if not event.accepted:
        raise AssistanceError("only accepted tentative cell moves can be evaluated")
    if isinstance(event.action, AssignCell):
        return AssignmentAtom(
            variable_id=event.action.variable_id,
            value_id=event.action.value_id,
        )
    if isinstance(event.action, ExcludeCell):
        return ExclusionAtom(
            variable_id=event.action.variable_id,
            value_id=event.action.value_id,
        )
    raise AssistanceError("the selected play event is not an evaluatable cell move")


def _current_atoms(session: LogicGridPlaySession) -> tuple[EvaluatableAtom, ...]:
    return tuple(
        sorted(
            (*session.assignments, *session.exclusions),
            key=canonical_json,
        )
    )


def _seal_move_evaluation(
    *,
    session: LogicGridPlaySession,
    event: PlayEvent,
    submitted_atom: EvaluatableAtom,
    status: MoveEvaluationStatus,
    authoritative_atom: EvaluatableAtom | None,
    verification: VerificationRecord | None,
    technique: LogicGridTechniqueEvidence | None,
    diagnostics: tuple[VerificationRecord, ...],
) -> LogicGridMoveEvaluation:
    unsigned = LogicGridMoveEvaluation.model_construct(
        schema_version=ASSISTANCE_SCHEMA_VERSION,
        attempt_id=session.attempt_id,
        puzzle_revision_id=session.puzzle_revision_id,
        source_session_hash=session.session_hash,
        source_event_id=event.event_id,
        submitted_atom=submitted_atom,
        status=status,
        authoritative_atom=authoritative_atom,
        verification=verification,
        technique=technique,
        diagnostic_verifications=diagnostics,
        evaluation_hash="0" * 64,
    )
    return LogicGridMoveEvaluation(
        schema_version=ASSISTANCE_SCHEMA_VERSION,
        attempt_id=session.attempt_id,
        puzzle_revision_id=session.puzzle_revision_id,
        source_session_hash=session.session_hash,
        source_event_id=event.event_id,
        submitted_atom=submitted_atom,
        status=status,
        authoritative_atom=authoritative_atom,
        verification=verification,
        technique=technique,
        diagnostic_verifications=diagnostics,
        evaluation_hash=compute_move_evaluation_hash(unsigned),
    )


def _seal_hint_result(
    *,
    session: LogicGridPlaySession,
    status: HintResultStatus,
    code: str,
    message: str,
    hint: LogicGridHint | None = None,
    blocking_evaluation: LogicGridMoveEvaluation | None = None,
) -> LogicGridHintResult:
    unsigned = LogicGridHintResult.model_construct(
        schema_version=ASSISTANCE_SCHEMA_VERSION,
        attempt_id=session.attempt_id,
        puzzle_revision_id=session.puzzle_revision_id,
        source_session_hash=session.session_hash,
        status=status,
        code=code,
        message=message,
        hint=hint,
        blocking_evaluation=blocking_evaluation,
        result_hash="0" * 64,
    )
    return LogicGridHintResult(
        schema_version=ASSISTANCE_SCHEMA_VERSION,
        attempt_id=session.attempt_id,
        puzzle_revision_id=session.puzzle_revision_id,
        source_session_hash=session.session_hash,
        status=status,
        code=code,
        message=message,
        hint=hint,
        blocking_evaluation=blocking_evaluation,
        result_hash=compute_hint_result_hash(unsigned),
    )


class LogicGridAssistanceService:
    """Evaluate tentative cells and disclose verified next steps without mutating play."""

    def __init__(self, coordinator: CrossVerificationCoordinator) -> None:
        self._coordinator = coordinator
        self._rules = logic_grid_rules()

    def _classify_atom(
        self,
        puzzle: LogicGridSpec,
        atom: EvaluatableAtom,
        *,
        purpose: str,
        timeout_ms: int,
    ) -> tuple[
        MoveEvaluationStatus,
        EvaluatableAtom | None,
        VerificationRecord | None,
        tuple[VerificationRecord, ...],
    ]:
        state = _initial_state(puzzle, purpose=f"{purpose}:global")
        claim = _proof_record(
            puzzle,
            state,
            atom,
            self._coordinator,
            purpose=f"{purpose}:claim",
            timeout_ms=timeout_ms,
        )
        opposite = _proof_record(
            puzzle,
            state,
            opposite_atom(atom),
            self._coordinator,
            purpose=f"{purpose}:opposite",
            timeout_ms=timeout_ms,
        )
        claim_verified = _is_cross_verified(claim)
        opposite_verified = _is_cross_verified(opposite)
        if claim_verified and not opposite_verified:
            return MoveEvaluationStatus.SUPPORTED, atom, claim, ()
        if opposite_verified and not claim_verified:
            return MoveEvaluationStatus.CONTRADICTED, opposite_atom(atom), opposite, ()
        statuses = {claim.decision.status, opposite.decision.status}
        status = (
            MoveEvaluationStatus.QUARANTINED
            if VerificationStatus.QUARANTINED in statuses or (claim_verified and opposite_verified)
            else MoveEvaluationStatus.INCONCLUSIVE
        )
        return status, None, None, (claim, opposite)

    def _state_from_supported_marks(
        self,
        puzzle: LogicGridSpec,
        session: LogicGridPlaySession,
        *,
        omit: EvaluatableAtom | None,
        timeout_ms: int,
    ) -> tuple[PuzzleState, tuple[tuple[EvaluatableAtom, MoveEvaluationStatus], ...]]:
        genesis = _initial_state(puzzle, purpose=f"hint:{session.session_hash}")
        given_atoms = set(puzzle.givens)
        supported: list[EvaluatableAtom] = []
        outcomes: list[tuple[EvaluatableAtom, MoveEvaluationStatus]] = []
        for atom in _current_atoms(session):
            if atom in given_atoms or atom == omit:
                continue
            status, _, _, _ = self._classify_atom(
                puzzle,
                atom,
                purpose=f"hint-mark:{session.session_hash}:{canonical_sha256(atom)}",
                timeout_ms=timeout_ms,
            )
            outcomes.append((atom, status))
            if status is MoveEvaluationStatus.SUPPORTED:
                supported.append(atom)

        candidates = {key: set(value) for key, value in genesis.candidate_domains.items()}
        asserted = set(genesis.asserted_atoms)
        for atom in supported:
            asserted.add(atom)
            if isinstance(atom, AssignmentAtom):
                candidates[atom.variable_id] = {atom.value_id}
            else:
                candidates[atom.variable_id].discard(atom.value_id)
        for variable_id, values in candidates.items():
            if not values:
                raise AssistanceError("cross-verified marks produced an impossible state")
            if len(values) == 1:
                asserted.add(AssignmentAtom(variable_id=variable_id, value_id=next(iter(values))))
        digest = canonical_sha256(
            {
                "puzzle_revision_id": puzzle.identity.revision_id,
                "session_hash": session.session_hash,
                "supported_atoms": supported,
            }
        )
        state = build_state(
            state_id=f"deductra:state:logic-grid-assistance:{digest}",
            puzzle_revision_id=puzzle.identity.revision_id,
            sequence_no=len(supported),
            branch_id=f"deductra:branch:logic-grid-assistance:{digest}",
            candidate_domains={key: frozenset(value) for key, value in candidates.items()},
            asserted_atoms=frozenset(asserted),
            rejected_atoms=frozenset(),
            active_constraint_ids=genesis.active_constraint_ids,
            contradiction_ids=(),
        )
        return state, tuple(outcomes)

    def _technique_for_atom(
        self,
        puzzle: LogicGridSpec,
        state: PuzzleState,
        atom: EvaluatableAtom,
        *,
        purpose: str,
        timeout_ms: int,
    ) -> LogicGridTechniqueEvidence | None:
        candidates = discover_rule_applications(puzzle, state, self._rules)
        rules = {item.reference: item for item in self._rules}
        for candidate in candidates:
            proposal = rules[candidate.rule].apply(candidate, state)
            if proposal.conclusions != (atom,):
                continue
            record = _proof_record(
                puzzle,
                state,
                atom,
                self._coordinator,
                purpose=purpose,
                assumptions=proposal.premises,
                timeout_ms=timeout_ms,
            )
            if _is_cross_verified(record):
                return _seal_technique_evidence(puzzle, candidate, proposal, record)
        return None

    def evaluate_move(
        self,
        puzzle: LogicGridSpec,
        session: LogicGridPlaySession,
        *,
        source_event_id: EventId,
        timeout_ms: int = 5_000,
    ) -> LogicGridMoveEvaluation:
        """Classify one retained accepted assignment or exclusion without changing play."""
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if session.puzzle_revision_id != puzzle.identity.revision_id:
            raise AssistanceError("session puzzle revision does not match the supplied puzzle")
        if (
            session.validation_mode is PlayValidationMode.EXAM
            and session.status is not PlaySessionStatus.COMPLETED
        ):
            raise AssistanceError("move evaluation is unavailable during an active exam attempt")
        event = next(
            (item for item in session.events if item.event_id == source_event_id),
            None,
        )
        if event is None:
            raise AssistanceError("the selected play event is not retained by this session")
        atom = _event_atom(event)
        status, authoritative, verification, diagnostics = self._classify_atom(
            puzzle,
            atom,
            purpose=f"move:{session.session_hash}:{event.event_id}",
            timeout_ms=timeout_ms,
        )
        technique = None
        if authoritative is not None:
            state, _ = self._state_from_supported_marks(
                puzzle,
                session,
                omit=atom,
                timeout_ms=timeout_ms,
            )
            technique = self._technique_for_atom(
                puzzle,
                state,
                authoritative,
                purpose=f"move-technique:{session.session_hash}:{event.event_id}",
                timeout_ms=timeout_ms,
            )
        return _seal_move_evaluation(
            session=session,
            event=event,
            submitted_atom=atom,
            status=status,
            authoritative_atom=authoritative,
            verification=verification,
            technique=technique,
            diagnostics=diagnostics,
        )

    def request_hint(
        self,
        puzzle: LogicGridSpec,
        session: LogicGridPlaySession,
        *,
        level: HintLevel,
        policy: ReasoningPolicy = ReasoningPolicy.TEACHING_FIRST,
        timeout_ms: int = 5_000,
    ) -> LogicGridHintResult:
        """Return one progressive hint derived from a cross-verified human-rule proposal."""
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if session.puzzle_revision_id != puzzle.identity.revision_id:
            raise AssistanceError("session puzzle revision does not match the supplied puzzle")
        if session.status is PlaySessionStatus.COMPLETED:
            return _seal_hint_result(
                session=session,
                status=HintResultStatus.ALREADY_COMPLETE,
                code="attempt_complete",
                message="This attempt is already independently verified as complete.",
            )
        if session.validation_mode is PlayValidationMode.EXAM:
            return _seal_hint_result(
                session=session,
                status=HintResultStatus.UNAVAILABLE_MODE,
                code="hints_withheld_in_exam",
                message="Hints are unavailable during an active exam attempt.",
            )
        state, outcomes = self._state_from_supported_marks(
            puzzle,
            session,
            omit=None,
            timeout_ms=timeout_ms,
        )
        for atom, outcome in outcomes:
            if outcome is MoveEvaluationStatus.CONTRADICTED:
                event = next(
                    item
                    for item in reversed(session.events)
                    if item.accepted
                    and isinstance(item.action, (AssignCell, ExcludeCell))
                    and _event_atom(item) == atom
                )
                evaluation = self.evaluate_move(
                    puzzle,
                    session,
                    source_event_id=event.event_id,
                    timeout_ms=timeout_ms,
                )
                return _seal_hint_result(
                    session=session,
                    status=HintResultStatus.CORRECTION_REQUIRED,
                    code="verified_correction_required",
                    message=(
                        "Resolve the identified contradicted cell before requesting a next step."
                    ),
                    blocking_evaluation=evaluation,
                )
        if any(outcome is MoveEvaluationStatus.QUARANTINED for _, outcome in outcomes):
            return _seal_hint_result(
                session=session,
                status=HintResultStatus.QUARANTINED,
                code="verification_quarantined",
                message="Independent verification disagreed, so no hint can be trusted.",
            )
        if any(outcome is MoveEvaluationStatus.INCONCLUSIVE for _, outcome in outcomes):
            return _seal_hint_result(
                session=session,
                status=HintResultStatus.INCONCLUSIVE,
                code="marks_inconclusive",
                message="Current marks could not all be independently verified.",
            )

        candidates = discover_rule_applications(puzzle, state, self._rules)
        candidate = select_rule_application(candidates, policy)
        if candidate is None:
            return _seal_hint_result(
                session=session,
                status=HintResultStatus.HUMAN_RULES_EXHAUSTED,
                code="human_rules_exhausted",
                message="No disclosed human-rule step is available from the verified play state.",
            )
        rule = next(item for item in self._rules if item.reference == candidate.rule)
        proposal = rule.apply(candidate, state)
        conclusion = proposal.conclusions[0]
        if not isinstance(conclusion, (AssignmentAtom, ExclusionAtom)):
            raise AssistanceError("the selected human rule did not propose a cell conclusion")
        verification = _proof_record(
            puzzle,
            state,
            conclusion,
            self._coordinator,
            purpose=f"hint:{session.session_hash}:{candidate.candidate_id}",
            assumptions=proposal.premises,
            timeout_ms=timeout_ms,
        )
        if verification.decision.status is VerificationStatus.QUARANTINED:
            return _seal_hint_result(
                session=session,
                status=HintResultStatus.QUARANTINED,
                code="verification_quarantined",
                message="Independent verification disagreed, so no hint can be trusted.",
            )
        if not _is_cross_verified(verification):
            return _seal_hint_result(
                session=session,
                status=HintResultStatus.INCONCLUSIVE,
                code="hint_inconclusive",
                message="The proposed human-rule step was not independently cross-verified.",
            )
        evidence = _seal_technique_evidence(puzzle, candidate, proposal, verification)
        disclosure = _build_disclosure(puzzle, evidence, level)
        unsigned = LogicGridHint.model_construct(
            schema_version=ASSISTANCE_SCHEMA_VERSION,
            attempt_id=session.attempt_id,
            puzzle_revision_id=session.puzzle_revision_id,
            source_session_hash=session.session_hash,
            kind=HintKind.PROGRESSION,
            evidence=evidence,
            disclosure=disclosure,
            hint_hash="0" * 64,
        )
        hint = LogicGridHint(
            schema_version=ASSISTANCE_SCHEMA_VERSION,
            attempt_id=session.attempt_id,
            puzzle_revision_id=session.puzzle_revision_id,
            source_session_hash=session.session_hash,
            kind=HintKind.PROGRESSION,
            evidence=evidence,
            disclosure=disclosure,
            hint_hash=compute_hint_hash(unsigned),
        )
        return _seal_hint_result(
            session=session,
            status=HintResultStatus.AVAILABLE,
            code="hint_available",
            message="A cross-verified human-rule hint is available.",
            hint=hint,
        )


def _labels(puzzle: LogicGridSpec) -> tuple[dict[str, str], dict[str, str]]:
    variable_labels = {item.variable_id: item.label for item in puzzle.variables}
    value_labels = {
        value.value_id: value.label for domain in puzzle.domains for value in domain.values
    }
    return variable_labels, value_labels


def _atom_text(
    atom: EvaluatableAtom,
    variable_labels: dict[str, str],
    value_labels: dict[str, str],
) -> str:
    variable = variable_labels.get(atom.variable_id, atom.variable_id)
    value = value_labels.get(atom.value_id, atom.value_id)
    if isinstance(atom, AssignmentAtom):
        return f"{variable} belongs with {value}."
    return f"{variable} cannot belong with {value}."


def _suggested_action(atom: EvaluatableAtom) -> AssignCell | ExcludeCell:
    if isinstance(atom, AssignmentAtom):
        return AssignCell(variable_id=atom.variable_id, value_id=atom.value_id)
    return ExcludeCell(variable_id=atom.variable_id, value_id=atom.value_id)


def _build_disclosure(
    puzzle: LogicGridSpec,
    evidence: LogicGridTechniqueEvidence,
    level: HintLevel,
) -> LogicGridHintDisclosure:
    variable_labels, value_labels = _labels(puzzle)
    focus = tuple(sorted(evidence.affected_variable_ids))
    clue_ids = tuple(sorted(item.clue_id for item in evidence.clues))
    focus_labels = ", ".join(variable_labels.get(item, item) for item in focus)
    premise_text = " ".join(
        _atom_text(item, variable_labels, value_labels)
        for item in evidence.premises
        if isinstance(item, (AssignmentAtom, ExclusionAtom))
    )
    conclusion_text = _atom_text(evidence.conclusion, variable_labels, value_labels)
    if level is HintLevel.REFLECTION:
        message = "Look for an item whose remaining row candidates are most constrained."
    elif level is HintLevel.ATTENTION:
        message = f"Focus on {focus_labels} and the highlighted supporting clue or category."
    elif level is HintLevel.TECHNIQUE:
        message = f"Use the {evidence.rule.title} technique for {focus_labels}."
    elif level is HintLevel.PREMISES:
        message = premise_text or "Use the currently verified candidate structure."
    elif level is HintLevel.DEDUCTION:
        message = f"What assignment or exclusion now follows for {focus_labels}?"
    elif level is HintLevel.EXPLANATION:
        message = conclusion_text
    else:
        message = f"Apply the cross-verified step: {conclusion_text}"
    return LogicGridHintDisclosure(
        level=level,
        message=message,
        focus_variable_ids=focus if level >= HintLevel.ATTENTION else (),
        clue_ids=clue_ids if level >= HintLevel.ATTENTION else (),
        rule_id=evidence.rule.rule_id if level >= HintLevel.TECHNIQUE else None,
        premises=evidence.premises if level >= HintLevel.PREMISES else (),
        conclusion=evidence.conclusion if level >= HintLevel.EXPLANATION else None,
        suggested_action=(
            _suggested_action(evidence.conclusion) if level is HintLevel.CONTINUE else None
        ),
    )


def default_logic_grid_assistance_service() -> LogicGridAssistanceService:
    """Compose the admitted independent Logic Grid verification backends."""
    return LogicGridAssistanceService(
        CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
    )
