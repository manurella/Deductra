"""Agent runtime port and deterministic disabled implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from deductra.agents.contracts import (
    AgentContextView,
    AgentOutput,
    AgentRequest,
    AgentRunAudit,
    AgentRunResult,
    AgentRunStatus,
    GuardrailOutcome,
    GuardrailReport,
)
from deductra.domain.ids import AgentId
from deductra.domain.serialization import canonical_sha256


@runtime_checkable
class AgentRuntime(Protocol):
    async def run_typed[OutputT: AgentOutput](
        self,
        agent_id: AgentId,
        request: AgentRequest,
        output_type: type[OutputT],
        context: AgentContextView,
    ) -> AgentRunResult[OutputT]:
        """Run an optional agent without granting canonical authority."""
        ...


class DisabledAgentRuntime:
    """Deterministic runtime used when remote agent enhancement is unavailable."""

    async def run_typed[OutputT: AgentOutput](
        self,
        agent_id: AgentId,
        request: AgentRequest,
        output_type: type[OutputT],
        context: AgentContextView,
    ) -> AgentRunResult[OutputT]:
        del output_type, context
        return AgentRunResult[OutputT](
            run_id=request.run_id,
            status=AgentRunStatus.DISABLED,
            output=None,
            failure_reason="optional agent runtime is disabled",
            guardrails=GuardrailReport(outcome=GuardrailOutcome.NOT_RUN),
            audit=AgentRunAudit(
                runtime="disabled",
                runtime_version="1.0.0",
                agent_id=agent_id,
                model=None,
                effort=None,
                prompt_version=None,
                requested_tools=request.requested_tools,
                used_tools=(),
                tracing_enabled=False,
                request_hash=canonical_sha256(request),
                output_hash=None,
            ),
        )
