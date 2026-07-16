"""Typed, immutable contracts at the optional agent-runtime boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from deductra.domain.base import DomainModel
from deductra.domain.ids import (
    AgentClaimId,
    AgentId,
    AgentRunId,
    CorrelationId,
    EvidenceId,
    PuzzleRevisionId,
    TraceId,
)
from deductra.reasoning.events import Sha256Digest
from deductra.verification.contracts import VerificationStatus


class AgentTaskKind(StrEnum):
    MODELLING = "modelling"
    PEDAGOGY = "pedagogy"
    AUDIT = "audit"
    LEARNING_ANALYSIS = "learning_analysis"
    NAVIGATION = "navigation"


class AgentRequest(DomainModel):
    run_id: AgentRunId
    correlation_id: CorrelationId
    task: AgentTaskKind
    input_text: str = Field(min_length=1, max_length=20_000)
    requested_tools: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_tools(self) -> Self:
        if len(self.requested_tools) != len(set(self.requested_tools)):
            raise ValueError("requested tool names must be unique")
        return self


class AgentEvidenceView(DomainModel):
    evidence_id: EvidenceId
    evidence_kind: str = Field(min_length=1)
    verification_status: VerificationStatus
    content_hash: Sha256Digest


class AgentContextView(DomainModel):
    """Minimal deterministic context exposed to an optional agent runtime."""

    puzzle_revision_id: PuzzleRevisionId | None = None
    trace_id: TraceId | None = None
    evidence: tuple[AgentEvidenceView, ...] = ()
    verified_solution_evidence_ids: tuple[EvidenceId, ...] = ()
    deterministic_result_hash: Sha256Digest | None = None
    deterministic_status: VerificationStatus = VerificationStatus.NOT_CHECKED
    allowed_tool_names: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("agent context evidence identifiers must be unique")
        if not set(self.verified_solution_evidence_ids) <= set(evidence_ids):
            raise ValueError("verified solution evidence must exist in the context")
        evidence = {item.evidence_id: item for item in self.evidence}
        if any(
            evidence[item].verification_status
            not in {
                VerificationStatus.BACKEND_VERIFIED,
                VerificationStatus.CROSS_VERIFIED,
            }
            for item in self.verified_solution_evidence_ids
        ):
            raise ValueError("verified solution evidence requires backend verification")
        if len(self.allowed_tool_names) != len(set(self.allowed_tool_names)):
            raise ValueError("context tool names must be unique")
        return self


class AgentClaimKind(StrEnum):
    FACTUAL = "factual"
    HYPOTHESIS = "hypothesis"
    SOLUTION = "solution"
    REPORT_FACT = "report_fact"


class AgentClaimMethod(StrEnum):
    DETERMINISTIC_EVIDENCE = "deterministic_evidence"
    HYPOTHESIS = "hypothesis"
    AGENT_SYNTHESIS = "agent_synthesis"
    HIDDEN_SEARCH = "hidden_search"


class AgentClaim(DomainModel):
    claim_id: AgentClaimId
    kind: AgentClaimKind
    method: AgentClaimMethod
    text: str = Field(min_length=1)
    evidence_ids: tuple[EvidenceId, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_shape(self) -> Self:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("agent claim evidence identifiers must be unique")
        return self


class AgentCommandKind(StrEnum):
    SUGGEST_HINT = "suggest_hint"
    REQUEST_VERIFICATION = "request_verification"
    PRESENT_VERIFIED_SOLUTION = "present_verified_solution"
    RECOMMEND_PRACTICE = "recommend_practice"
    APPLY_DOMAIN_EVENT = "apply_domain_event"
    COMMIT_SOLUTION = "commit_solution"
    CHANGE_DIFFICULTY = "change_difficulty"
    WRITE_REPORT_FACT = "write_report_fact"


class AgentCommandProposal(DomainModel):
    kind: AgentCommandKind
    rationale: str = Field(min_length=1)
    evidence_ids: tuple[EvidenceId, ...] = ()


class AgentOutput(DomainModel):
    claims: tuple[AgentClaim, ...] = ()
    commands: tuple[AgentCommandProposal, ...] = ()
    uncertainty: str | None = None
    refusal_reason: str | None = None

    @model_validator(mode="after")
    def validate_nonempty_output(self) -> Self:
        if not (self.claims or self.commands or self.uncertainty or self.refusal_reason):
            raise ValueError("agent output must contain a proposal, uncertainty, or refusal")
        claim_ids = tuple(item.claim_id for item in self.claims)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("agent claim identifiers must be unique")
        return self


class AgentPolicy(DomainModel):
    agent_id: AgentId
    allowed_tasks: tuple[AgentTaskKind, ...]
    allowed_tool_names: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if not self.allowed_tasks:
            raise ValueError("agent policy requires at least one allowed task")
        if len(self.allowed_tasks) != len(set(self.allowed_tasks)):
            raise ValueError("allowed tasks must be unique")
        if len(self.allowed_tool_names) != len(set(self.allowed_tool_names)):
            raise ValueError("allowlisted tool names must be unique")
        return self


class GuardrailCode(StrEnum):
    TASK_NOT_ALLOWED = "task_not_allowed"
    TOOL_NOT_ALLOWED = "tool_not_allowed"
    TOOL_USE_NOT_DECLARED = "tool_use_not_declared"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    UNACCEPTED_EVIDENCE = "unaccepted_evidence"
    UNCITED_FACT = "uncited_fact"
    ATTEMPTED_STATE_MUTATION = "attempted_state_mutation"
    UNVERIFIED_SOLUTION = "unverified_solution"
    DETERMINISTIC_CONFLICT = "deterministic_conflict"
    HIDDEN_SEARCH = "hidden_search"


class GuardrailFinding(DomainModel):
    code: GuardrailCode
    message: str = Field(min_length=1)
    subject_id: str | None = None


class GuardrailOutcome(StrEnum):
    PASSED = "passed"
    REJECTED = "rejected"
    NOT_RUN = "not_run"


class GuardrailReport(DomainModel):
    outcome: GuardrailOutcome
    findings: tuple[GuardrailFinding, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.outcome is GuardrailOutcome.REJECTED and not self.findings:
            raise ValueError("rejected guardrail reports require findings")
        if self.outcome is not GuardrailOutcome.REJECTED and self.findings:
            raise ValueError("only rejected guardrail reports may contain findings")
        return self


class AgentRunStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DISABLED = "disabled"
    FAILED = "failed"


class AgentRunAudit(DomainModel):
    runtime: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    agent_id: AgentId
    model: str | None
    effort: str | None
    prompt_version: str | None
    requested_tools: tuple[str, ...]
    used_tools: tuple[str, ...]
    tracing_enabled: bool
    request_hash: Sha256Digest
    output_hash: Sha256Digest | None


class AgentRunResult[OutputT: AgentOutput](DomainModel):
    run_id: AgentRunId
    status: AgentRunStatus
    output: OutputT | None
    failure_reason: str | None = None
    guardrails: GuardrailReport
    audit: AgentRunAudit

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.status is AgentRunStatus.ACCEPTED:
            if (
                self.output is None
                or self.failure_reason is not None
                or self.guardrails.outcome is not GuardrailOutcome.PASSED
            ):
                raise ValueError("accepted runs require output that passed guardrails")
        elif self.output is not None:
            raise ValueError("non-accepted runs cannot expose agent output")
        if self.status is AgentRunStatus.REJECTED and (
            self.guardrails.outcome is not GuardrailOutcome.REJECTED
        ):
            raise ValueError("rejected runs require rejected guardrails")
        if self.status is AgentRunStatus.DISABLED and (
            self.guardrails.outcome is not GuardrailOutcome.NOT_RUN
        ):
            raise ValueError("disabled runs require not-run guardrails")
        if self.status in {AgentRunStatus.DISABLED, AgentRunStatus.FAILED}:
            if not self.failure_reason:
                raise ValueError("disabled and failed runs require a reason")
        elif self.failure_reason is not None:
            raise ValueError("only disabled and failed runs may carry a failure reason")
        return self
