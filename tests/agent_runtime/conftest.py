from __future__ import annotations

from deductra.agents.contracts import (
    AgentContextView,
    AgentEvidenceView,
    AgentPolicy,
    AgentRequest,
    AgentTaskKind,
)
from deductra.verification.contracts import VerificationStatus

EVIDENCE_ID = "evidence:verified:solution"


def make_request(*, tools: tuple[str, ...] = ()) -> AgentRequest:
    return AgentRequest(
        run_id="agent-run:1",
        correlation_id="correlation:1",
        task=AgentTaskKind.AUDIT,
        input_text="Review the deterministic result and return a grounded proposal.",
        requested_tools=tools,
    )


def make_context(
    *,
    status: VerificationStatus = VerificationStatus.CROSS_VERIFIED,
    tools: tuple[str, ...] = ("verify_deduction",),
) -> AgentContextView:
    return AgentContextView(
        puzzle_revision_id="puzzle-revision:1",
        trace_id="trace:1",
        evidence=(
            AgentEvidenceView(
                evidence_id=EVIDENCE_ID,
                evidence_kind="verification_record",
                verification_status=status,
                content_hash="1" * 64,
            ),
        ),
        verified_solution_evidence_ids=(
            (EVIDENCE_ID,)
            if status
            in {
                VerificationStatus.BACKEND_VERIFIED,
                VerificationStatus.CROSS_VERIFIED,
            }
            else ()
        ),
        deterministic_result_hash="2" * 64,
        deterministic_status=status,
        allowed_tool_names=tools,
    )


def make_policy(*, tools: tuple[str, ...] = ("verify_deduction",)) -> AgentPolicy:
    return AgentPolicy(
        agent_id="agent:auditor",
        allowed_tasks=(AgentTaskKind.AUDIT,),
        allowed_tool_names=tools,
    )
