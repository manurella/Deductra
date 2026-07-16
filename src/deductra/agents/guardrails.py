"""Fail-closed validation for agent requests, tools, claims, and proposals."""

from __future__ import annotations

from deductra.agents.contracts import (
    AgentClaimKind,
    AgentClaimMethod,
    AgentCommandKind,
    AgentContextView,
    AgentOutput,
    AgentPolicy,
    AgentRequest,
    GuardrailCode,
    GuardrailFinding,
    GuardrailOutcome,
    GuardrailReport,
)
from deductra.verification.contracts import VerificationStatus

_ACCEPTED_EVIDENCE = {
    VerificationStatus.STRUCTURALLY_VALID,
    VerificationStatus.BACKEND_VERIFIED,
    VerificationStatus.CROSS_VERIFIED,
}
_FACTUAL_CLAIMS = {
    AgentClaimKind.FACTUAL,
    AgentClaimKind.SOLUTION,
    AgentClaimKind.REPORT_FACT,
}
_MUTATING_COMMANDS = {
    AgentCommandKind.APPLY_DOMAIN_EVENT,
    AgentCommandKind.COMMIT_SOLUTION,
    AgentCommandKind.CHANGE_DIFFICULTY,
    AgentCommandKind.WRITE_REPORT_FACT,
}


def validate_agent_request(
    request: AgentRequest,
    context: AgentContextView,
    policy: AgentPolicy,
) -> GuardrailReport:
    """Validate task and tool scope before any remote model invocation."""
    findings: list[GuardrailFinding] = []
    if request.task not in policy.allowed_tasks:
        findings.append(
            GuardrailFinding(
                code=GuardrailCode.TASK_NOT_ALLOWED,
                message=f"task {request.task} is not allowed for this agent",
            )
        )
    allowed_tools = set(policy.allowed_tool_names) & set(context.allowed_tool_names)
    for tool_name in request.requested_tools:
        if tool_name not in allowed_tools:
            findings.append(
                GuardrailFinding(
                    code=GuardrailCode.TOOL_NOT_ALLOWED,
                    message=f"tool {tool_name} is outside the effective allowlist",
                    subject_id=tool_name,
                )
            )
    return _report(findings)


def validate_agent_output(
    output: AgentOutput,
    request: AgentRequest,
    context: AgentContextView,
    policy: AgentPolicy,
    *,
    used_tools: tuple[str, ...] = (),
) -> GuardrailReport:
    """Reject unsupported facts, authority attempts, conflicts, and tool escapes."""
    findings: list[GuardrailFinding] = []
    evidence = {item.evidence_id: item for item in context.evidence}
    declared_tools = set(request.requested_tools)
    effective_tools = set(policy.allowed_tool_names) & set(context.allowed_tool_names)

    for tool_name in used_tools:
        if tool_name not in effective_tools:
            findings.append(
                GuardrailFinding(
                    code=GuardrailCode.TOOL_NOT_ALLOWED,
                    message=f"used tool {tool_name} is outside the effective allowlist",
                    subject_id=tool_name,
                )
            )
        elif tool_name not in declared_tools:
            findings.append(
                GuardrailFinding(
                    code=GuardrailCode.TOOL_USE_NOT_DECLARED,
                    message=f"used tool {tool_name} was not requested",
                    subject_id=tool_name,
                )
            )

    for claim in output.claims:
        if claim.method is AgentClaimMethod.HIDDEN_SEARCH:
            findings.append(
                GuardrailFinding(
                    code=GuardrailCode.HIDDEN_SEARCH,
                    message=f"claim {claim.claim_id} discloses hidden search",
                    subject_id=claim.claim_id,
                )
            )
        if (
            claim.kind in _FACTUAL_CLAIMS
            and claim.method is not AgentClaimMethod.DETERMINISTIC_EVIDENCE
        ):
            findings.append(
                GuardrailFinding(
                    code=GuardrailCode.DETERMINISTIC_CONFLICT,
                    message=f"claim {claim.claim_id} is not derived from deterministic evidence",
                    subject_id=claim.claim_id,
                )
            )
        if claim.kind in _FACTUAL_CLAIMS and not claim.evidence_ids:
            findings.append(
                GuardrailFinding(
                    code=GuardrailCode.UNCITED_FACT,
                    message=f"claim {claim.claim_id} has no evidence",
                    subject_id=claim.claim_id,
                )
            )
        for evidence_id in claim.evidence_ids:
            item = evidence.get(evidence_id)
            if item is None:
                findings.append(
                    GuardrailFinding(
                        code=GuardrailCode.UNKNOWN_EVIDENCE,
                        message=f"claim {claim.claim_id} cites unknown evidence {evidence_id}",
                        subject_id=claim.claim_id,
                    )
                )
            elif item.verification_status not in _ACCEPTED_EVIDENCE:
                findings.append(
                    GuardrailFinding(
                        code=GuardrailCode.UNACCEPTED_EVIDENCE,
                        message=f"claim {claim.claim_id} cites unaccepted evidence {evidence_id}",
                        subject_id=claim.claim_id,
                    )
                )
        if claim.kind is AgentClaimKind.SOLUTION:
            _validate_solution_evidence(
                claim.claim_id,
                claim.evidence_ids,
                context,
                findings,
            )

    for command in output.commands:
        if command.kind in _MUTATING_COMMANDS:
            findings.append(
                GuardrailFinding(
                    code=GuardrailCode.ATTEMPTED_STATE_MUTATION,
                    message=f"agent command {command.kind} requests canonical authority",
                    subject_id=command.kind,
                )
            )
        if command.kind is AgentCommandKind.PRESENT_VERIFIED_SOLUTION:
            _validate_solution_evidence(
                command.kind,
                command.evidence_ids,
                context,
                findings,
            )
        for evidence_id in command.evidence_ids:
            item = evidence.get(evidence_id)
            if item is None:
                findings.append(
                    GuardrailFinding(
                        code=GuardrailCode.UNKNOWN_EVIDENCE,
                        message=f"command {command.kind} cites unknown evidence {evidence_id}",
                        subject_id=command.kind,
                    )
                )
            elif item.verification_status not in _ACCEPTED_EVIDENCE:
                findings.append(
                    GuardrailFinding(
                        code=GuardrailCode.UNACCEPTED_EVIDENCE,
                        message=f"command {command.kind} cites unaccepted evidence {evidence_id}",
                        subject_id=command.kind,
                    )
                )

    return _report(findings)


def _validate_solution_evidence(
    subject_id: str,
    evidence_ids: tuple[str, ...],
    context: AgentContextView,
    findings: list[GuardrailFinding],
) -> None:
    verified = set(context.verified_solution_evidence_ids)
    if not evidence_ids or not set(evidence_ids) <= verified:
        findings.append(
            GuardrailFinding(
                code=GuardrailCode.UNVERIFIED_SOLUTION,
                message=f"{subject_id} is not grounded in verified solution evidence",
                subject_id=subject_id,
            )
        )
    if context.deterministic_status not in {
        VerificationStatus.BACKEND_VERIFIED,
        VerificationStatus.CROSS_VERIFIED,
    }:
        findings.append(
            GuardrailFinding(
                code=GuardrailCode.DETERMINISTIC_CONFLICT,
                message=f"{subject_id} conflicts with the deterministic verification status",
                subject_id=subject_id,
            )
        )


def _report(findings: list[GuardrailFinding]) -> GuardrailReport:
    if findings:
        return GuardrailReport(
            outcome=GuardrailOutcome.REJECTED,
            findings=tuple(findings),
        )
    return GuardrailReport(outcome=GuardrailOutcome.PASSED)
