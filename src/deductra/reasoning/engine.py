"""Verified deterministic human-rule solve loop with explicit stalled outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import model_validator

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.base import DomainModel
from deductra.domain.ids import CertificateId, ConstraintId, ObligationId, RuleCandidateId
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.events import (
    CandidatesEliminated,
    EventEnvelope,
    ProducerRef,
    Sha256Digest,
    ValueAssigned,
)
from deductra.reasoning.integrity import seal_event
from deductra.reasoning.policy import ReasoningPolicy, select_rule_application
from deductra.reasoning.rules import (
    ProposedDeduction,
    ReasoningRule,
    RuleApplicationCandidate,
    RuleContractError,
    RuleReference,
    discover_rule_applications,
)
from deductra.reasoning.state import PuzzleState, validate_state


class HumanSolveStatus(StrEnum):
    """Terminal classification for one bounded human-rule run."""

    SOLVED = "solved"
    STALLED = "stalled"
    INCONCLUSIVE = "inconclusive"
    QUARANTINED = "quarantined"
    LIMIT_REACHED = "limit_reached"


class DeductionAuthorityStatus(StrEnum):
    """Backend-neutral authority outcome consumed by the human loop."""

    BACKEND_VERIFIED = "backend_verified"
    CROSS_VERIFIED = "cross_verified"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    QUARANTINED = "quarantined"


class DeductionAuthorityResult(DomainModel):
    """Stable authority response with a state only for accepted deductions."""

    status: DeductionAuthorityStatus
    obligation_id: ObligationId | None = None
    certificate_ids: tuple[CertificateId, ...] = ()
    reason: str
    result_state: PuzzleState | None = None

    @model_validator(mode="after")
    def validate_authority(self) -> Self:
        accepted = self.status in {
            DeductionAuthorityStatus.BACKEND_VERIFIED,
            DeductionAuthorityStatus.CROSS_VERIFIED,
        }
        if accepted != (self.result_state is not None):
            raise ValueError("accepted authority and result_state must appear together")
        return self


@runtime_checkable
class DeductionAuthority(Protocol):
    """Port that proves a proposed event and applies verified reduction."""

    def evaluate(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
        proposal: ProposedDeduction,
        event: EventEnvelope,
        *,
        timeout_ms: int,
    ) -> DeductionAuthorityResult: ...


class HumanSolveContext(DomainModel):
    """Caller-owned deterministic envelope context for emitted deduction events."""

    trace_id: str
    correlation_id: str
    producer: ProducerRef
    occurred_at: datetime
    previous_event_hash: Sha256Digest
    schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def require_timezone(self) -> Self:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        return self


class HumanReasoningAttempt(DomainModel):
    """Stable logical record of one selected human-rule candidate."""

    candidate_id: RuleCandidateId
    source_state_hash: Sha256Digest
    rule: RuleReference
    premises: tuple[Atom, ...] = ()
    conclusions: tuple[Atom, ...] = ()
    supporting_constraints: tuple[ConstraintId, ...] = ()
    proposal_hash: Sha256Digest | None = None
    obligation_id: ObligationId | None = None
    verification_status: DeductionAuthorityStatus
    certificate_ids: tuple[CertificateId, ...] = ()
    reason: str
    event_id: str | None = None
    result_state_hash: Sha256Digest | None = None

    @model_validator(mode="after")
    def validate_attempt_evidence(self) -> Self:
        if self.verification_status in {
            DeductionAuthorityStatus.BACKEND_VERIFIED,
            DeductionAuthorityStatus.CROSS_VERIFIED,
        } and (
            self.proposal_hash is None
            or self.obligation_id is None
            or not self.certificate_ids
            or len(self.conclusions) != 1
            or self.event_id is None
            or self.result_state_hash is None
        ):
            raise ValueError("verified attempts require complete deduction evidence")
        return self


class HumanSolveTrace(DomainModel):
    """Canonical logical trace of a bounded human-rule solve run."""

    trace_id: str
    puzzle_revision_id: str
    policy: ReasoningPolicy
    status: HumanSolveStatus
    stalled_reason: Literal["HUMAN_RULES_EXHAUSTED", "MAX_STEPS_REACHED"] | None = None
    initial_state_hash: Sha256Digest
    final_state_hash: Sha256Digest
    attempts: tuple[HumanReasoningAttempt, ...]
    events: tuple[EventEnvelope, ...]
    trace_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        if self.status is HumanSolveStatus.STALLED:
            if self.stalled_reason != "HUMAN_RULES_EXHAUSTED":
                raise ValueError("stalled traces require HUMAN_RULES_EXHAUSTED")
        elif self.status is HumanSolveStatus.LIMIT_REACHED:
            if self.stalled_reason != "MAX_STEPS_REACHED":
                raise ValueError("limited traces require MAX_STEPS_REACHED")
        elif self.stalled_reason is not None:
            raise ValueError("non-stalled traces cannot carry a stalled reason")
        if self.trace_hash != compute_human_trace_hash(self):
            raise ValueError("trace_hash does not match canonical trace contents")
        return self


def compute_human_trace_hash(trace: HumanSolveTrace) -> str:
    """Hash every canonical logical-trace field except its self-digest."""
    return canonical_sha256(trace.model_dump(mode="json", exclude={"trace_hash"}))


def _build_trace(
    *,
    context: HumanSolveContext,
    puzzle: PuzzleSpec,
    policy: ReasoningPolicy,
    status: HumanSolveStatus,
    stalled_reason: Literal["HUMAN_RULES_EXHAUSTED", "MAX_STEPS_REACHED"] | None,
    initial_state_hash: str,
    final_state_hash: str,
    attempts: Sequence[HumanReasoningAttempt],
    events: Sequence[EventEnvelope],
) -> HumanSolveTrace:
    unsigned = HumanSolveTrace.model_construct(
        trace_id=context.trace_id,
        puzzle_revision_id=puzzle.identity.revision_id,
        policy=policy,
        status=status,
        stalled_reason=stalled_reason,
        initial_state_hash=initial_state_hash,
        final_state_hash=final_state_hash,
        attempts=tuple(attempts),
        events=tuple(events),
        trace_hash="0" * 64,
    )
    return HumanSolveTrace(
        trace_id=context.trace_id,
        puzzle_revision_id=puzzle.identity.revision_id,
        policy=policy,
        status=status,
        stalled_reason=stalled_reason,
        initial_state_hash=initial_state_hash,
        final_state_hash=final_state_hash,
        attempts=tuple(attempts),
        events=tuple(events),
        trace_hash=compute_human_trace_hash(unsigned),
    )


def _validate_proposal(
    puzzle: PuzzleSpec,
    state: PuzzleState,
    candidate: RuleApplicationCandidate,
    proposal: ProposedDeduction,
) -> AssignmentAtom | ExclusionAtom:
    if proposal.candidate_id != candidate.candidate_id or proposal.rule != candidate.rule:
        raise RuleContractError("proposal identity does not match the selected candidate")
    if proposal.source_state_hash != state.state_hash:
        raise RuleContractError("proposal source state is stale")
    if proposal.premises != candidate.premises:
        raise RuleContractError("proposal premises differ from discovery")
    if proposal.affected_variables != candidate.affected_variables:
        raise RuleContractError("proposal affected variables differ from discovery")
    if proposal.supporting_constraints != candidate.supporting_constraints:
        raise RuleContractError("proposal supporting constraints differ from discovery")
    if len(proposal.conclusions) != 1:
        raise RuleContractError("CR-005 human rules require exactly one conclusion")
    if any(item not in state.asserted_atoms for item in proposal.premises):
        raise RuleContractError("proposal cites a premise absent from the source state")
    if not set(proposal.supporting_constraints) <= set(state.active_constraint_ids):
        raise RuleContractError("proposal cites an inactive constraint")
    variable_ids = {item.variable_id for item in puzzle.variables}
    if not set(proposal.affected_variables) <= variable_ids:
        raise RuleContractError("proposal affects an unknown variable")

    conclusion = proposal.conclusions[0]
    if not isinstance(conclusion, (AssignmentAtom, ExclusionAtom)):
        raise RuleContractError("CR-005 supports assignment and elimination conclusions only")
    if conclusion.variable_id not in proposal.affected_variables:
        raise RuleContractError("conclusion variable is absent from affected variables")
    candidates = state.candidate_domains.get(conclusion.variable_id)
    if candidates is None or conclusion.value_id not in candidates:
        raise RuleContractError("conclusion references an unavailable candidate")
    if isinstance(conclusion, AssignmentAtom) and len(candidates) == 1:
        raise RuleContractError("assignment proposal is already present in the source state")
    if isinstance(conclusion, ExclusionAtom) and len(candidates) == 1:
        raise RuleContractError("elimination proposal would empty the candidate domain")
    return conclusion


class HumanReasoningEngine:
    """Discover, select, verify, and reduce only disclosed human-rule deductions."""

    def __init__(
        self,
        rules: Sequence[ReasoningRule],
        authority: DeductionAuthority,
    ) -> None:
        self._rules = tuple(rules)
        self._authority = authority
        identities = tuple((item.reference.rule_id, item.reference.rule_version) for item in rules)
        if len(identities) != len(set(identities)):
            raise RuleContractError("reasoning rule identities must be unique")

    def solve(
        self,
        puzzle: PuzzleSpec,
        initial_state: PuzzleState,
        context: HumanSolveContext,
        *,
        policy: ReasoningPolicy = ReasoningPolicy.FAMILY_CANONICAL,
        max_steps: int = 1_000,
        timeout_ms: int = 5_000,
    ) -> HumanSolveTrace:
        """Run human rules without search fallback or unverified state changes."""
        if max_steps <= 0 or timeout_ms <= 0:
            raise ValueError("max_steps and timeout_ms must be positive")
        validation = validate_state(initial_state, puzzle)
        if not validation.valid:
            raise RuleContractError(f"initial state is invalid: {validation.violations}")

        current = initial_state
        previous_event_hash = context.previous_event_hash
        attempts: list[HumanReasoningAttempt] = []
        events: list[EventEnvelope] = []
        attempted: set[tuple[str, str]] = set()
        applied_steps = 0

        while not current.solved and applied_steps < max_steps:
            candidates = tuple(
                item
                for item in discover_rule_applications(puzzle, current, self._rules)
                if (current.state_hash, item.candidate_id) not in attempted
            )
            candidate = select_rule_application(candidates, policy)
            if candidate is None:
                return _build_trace(
                    context=context,
                    puzzle=puzzle,
                    policy=policy,
                    status=HumanSolveStatus.STALLED,
                    stalled_reason="HUMAN_RULES_EXHAUSTED",
                    initial_state_hash=initial_state.state_hash,
                    final_state_hash=current.state_hash,
                    attempts=attempts,
                    events=events,
                )
            attempted.add((current.state_hash, candidate.candidate_id))
            rule = next(item for item in self._rules if item.reference == candidate.rule)
            try:
                proposal = rule.apply(candidate, current)
                conclusion = _validate_proposal(puzzle, current, candidate, proposal)
            except (RuleContractError, ValueError) as error:
                attempts.append(
                    HumanReasoningAttempt(
                        candidate_id=candidate.candidate_id,
                        source_state_hash=current.state_hash,
                        rule=candidate.rule,
                        premises=candidate.premises,
                        supporting_constraints=candidate.supporting_constraints,
                        verification_status=DeductionAuthorityStatus.REJECTED,
                        reason=f"invalid rule proposal: {error}",
                    )
                )
                continue

            proposal_hash = canonical_sha256(proposal)
            identity = canonical_sha256(
                {
                    "candidate_id": candidate.candidate_id,
                    "sequence_no": current.sequence_no + 1,
                    "source_state_hash": current.state_hash,
                    "trace_id": context.trace_id,
                }
            )
            result_state_id = f"deductra:state:{identity}"
            payload = (
                ValueAssigned(
                    variable_id=conclusion.variable_id,
                    value_id=conclusion.value_id,
                    source_state_hash=current.state_hash,
                    result_state_id=result_state_id,
                    origin="human_rule",
                )
                if isinstance(conclusion, AssignmentAtom)
                else CandidatesEliminated(
                    variable_id=conclusion.variable_id,
                    value_ids=(conclusion.value_id,),
                    source_state_hash=current.state_hash,
                    result_state_id=result_state_id,
                    origin="human_rule",
                )
            )
            event = seal_event(
                event_id=f"deductra:event:{identity}",
                trace_id=context.trace_id,
                puzzle_revision_id=puzzle.identity.revision_id,
                branch_id=current.branch_id,
                sequence_no=current.sequence_no + 1,
                schema_version=context.schema_version,
                occurred_at=context.occurred_at,
                producer=context.producer,
                correlation_id=context.correlation_id,
                previous_event_hash=previous_event_hash,
                payload=payload,
            )
            authority = self._authority.evaluate(
                puzzle, current, proposal, event, timeout_ms=timeout_ms
            )
            if authority.result_state is None:
                attempts.append(
                    HumanReasoningAttempt(
                        candidate_id=candidate.candidate_id,
                        source_state_hash=current.state_hash,
                        rule=proposal.rule,
                        premises=proposal.premises,
                        conclusions=proposal.conclusions,
                        supporting_constraints=proposal.supporting_constraints,
                        proposal_hash=proposal_hash,
                        obligation_id=authority.obligation_id,
                        verification_status=authority.status,
                        certificate_ids=authority.certificate_ids,
                        reason=authority.reason,
                    )
                )
                if authority.status in {
                    DeductionAuthorityStatus.INCONCLUSIVE,
                    DeductionAuthorityStatus.QUARANTINED,
                }:
                    status = (
                        HumanSolveStatus.INCONCLUSIVE
                        if authority.status is DeductionAuthorityStatus.INCONCLUSIVE
                        else HumanSolveStatus.QUARANTINED
                    )
                    return _build_trace(
                        context=context,
                        puzzle=puzzle,
                        policy=policy,
                        status=status,
                        stalled_reason=None,
                        initial_state_hash=initial_state.state_hash,
                        final_state_hash=current.state_hash,
                        attempts=attempts,
                        events=events,
                    )
                continue

            result = authority.result_state
            result_validation = validate_state(result, puzzle)
            if not result_validation.valid:
                raise RuleContractError(
                    f"verified rule produced invalid state: {result_validation.violations}"
                )
            attempts.append(
                HumanReasoningAttempt(
                    candidate_id=candidate.candidate_id,
                    source_state_hash=current.state_hash,
                    rule=proposal.rule,
                    premises=proposal.premises,
                    conclusions=proposal.conclusions,
                    supporting_constraints=proposal.supporting_constraints,
                    proposal_hash=proposal_hash,
                    obligation_id=authority.obligation_id,
                    verification_status=authority.status,
                    certificate_ids=authority.certificate_ids,
                    reason=authority.reason,
                    event_id=event.event_id,
                    result_state_hash=result.state_hash,
                )
            )
            events.append(event)
            current = result
            previous_event_hash = event.event_hash
            applied_steps += 1

        status = HumanSolveStatus.SOLVED if current.solved else HumanSolveStatus.LIMIT_REACHED
        return _build_trace(
            context=context,
            puzzle=puzzle,
            policy=policy,
            status=status,
            stalled_reason=None if current.solved else "MAX_STEPS_REACHED",
            initial_state_hash=initial_state.state_hash,
            final_state_hash=current.state_hash,
            attempts=attempts,
            events=events,
        )
