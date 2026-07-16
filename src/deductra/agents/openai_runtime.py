"""OpenAI Agents SDK adapter isolated behind Deductra's runtime port."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import version
from types import MappingProxyType
from typing import Literal, Protocol, Self, cast

from pydantic import Field, model_validator

from deductra.agents.contracts import (
    AgentContextView,
    AgentOutput,
    AgentPolicy,
    AgentRequest,
    AgentRunAudit,
    AgentRunResult,
    AgentRunStatus,
    GuardrailOutcome,
    GuardrailReport,
)
from deductra.agents.guardrails import validate_agent_output, validate_agent_request
from deductra.domain.base import DomainModel
from deductra.domain.ids import AgentId
from deductra.domain.serialization import canonical_json, canonical_sha256

type ReasoningEffort = Literal["none", "low", "medium", "high"]


class OpenAIAgentDefinition(DomainModel):
    agent_id: AgentId
    name: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    model: str = Field(min_length=1)
    effort: ReasoningEffort
    prompt_version: str = Field(min_length=1)
    policy: AgentPolicy

    @model_validator(mode="after")
    def match_policy_identity(self) -> Self:
        if self.policy.agent_id != self.agent_id:
            raise ValueError("agent definition and policy identifiers must match")
        return self


@dataclass(frozen=True, slots=True)
class OpenAIToolBinding:
    name: str
    sdk_tool: object

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool binding name cannot be empty")


@dataclass(frozen=True, slots=True)
class OpenAIAgentRegistration:
    definition: OpenAIAgentDefinition
    tools: tuple[OpenAIToolBinding, ...] = ()
    tracing_enabled: bool = False

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.tools)
        if len(names) != len(set(names)):
            raise ValueError("registered tool names must be unique")
        if set(names) != set(self.definition.policy.allowed_tool_names):
            raise ValueError("registered tools must exactly match the agent policy allowlist")


@dataclass(frozen=True, slots=True)
class SdkRunResult[OutputT: AgentOutput]:
    output: OutputT
    used_tools: tuple[str, ...]


class OpenAISdkBridge(Protocol):
    async def run[OutputT: AgentOutput](
        self,
        registration: OpenAIAgentRegistration,
        request: AgentRequest,
        output_type: type[OutputT],
        context: AgentContextView,
        tools: tuple[object, ...],
    ) -> SdkRunResult[OutputT]:
        """Execute one SDK run and return only typed output plus tool-use names."""
        ...


class DefaultOpenAISdkBridge:
    """Narrow dynamic bridge that prevents SDK types leaking into core contracts."""

    async def run[OutputT: AgentOutput](
        self,
        registration: OpenAIAgentRegistration,
        request: AgentRequest,
        output_type: type[OutputT],
        context: AgentContextView,
        tools: tuple[object, ...],
    ) -> SdkRunResult[OutputT]:
        sdk = import_module("agents")
        openai_types = import_module("openai.types.shared")
        agent_type = sdk.Agent
        model_settings_type = sdk.ModelSettings
        run_config_type = sdk.RunConfig
        runner = sdk.Runner
        reasoning_type = openai_types.Reasoning
        definition = registration.definition
        agent = agent_type(
            name=definition.name,
            instructions=definition.instructions,
            model=definition.model,
            model_settings=model_settings_type(
                reasoning=reasoning_type(effort=definition.effort),
                verbosity="low",
            ),
            tools=list(tools),
            output_type=output_type,
        )
        model_input = canonical_json(
            {
                "request": request,
                "context": context,
            }
        )
        result = await runner.run(
            agent,
            model_input,
            context=context,
            run_config=run_config_type(
                tracing_disabled=not registration.tracing_enabled,
                trace_include_sensitive_data=False,
                workflow_name="Deductra typed agent workflow",
            ),
        )
        final_output = getattr(result, "final_output", None)
        if isinstance(final_output, output_type):
            output = final_output
        else:
            output = output_type.model_validate(final_output)
        return SdkRunResult(
            output=output,
            used_tools=_used_tool_names(getattr(result, "new_items", ())),
        )


class OpenAIAgentsRuntime:
    """Optional remote runtime with preflight and post-output guardrails."""

    def __init__(
        self,
        registrations: tuple[OpenAIAgentRegistration, ...],
        *,
        bridge: OpenAISdkBridge | None = None,
    ) -> None:
        ids = tuple(item.definition.agent_id for item in registrations)
        if len(ids) != len(set(ids)):
            raise ValueError("agent registration identifiers must be unique")
        self._registrations: Mapping[AgentId, OpenAIAgentRegistration] = MappingProxyType(
            {item.definition.agent_id: item for item in registrations}
        )
        self._bridge = bridge or DefaultOpenAISdkBridge()

    async def run_typed[OutputT: AgentOutput](
        self,
        agent_id: AgentId,
        request: AgentRequest,
        output_type: type[OutputT],
        context: AgentContextView,
    ) -> AgentRunResult[OutputT]:
        registration = self._registrations.get(agent_id)
        if registration is None:
            raise ValueError(f"agent {agent_id} is not registered")
        definition = registration.definition
        preflight = validate_agent_request(request, context, definition.policy)
        if preflight.outcome is GuardrailOutcome.REJECTED:
            return self._result(
                registration,
                request,
                status=AgentRunStatus.REJECTED,
                output=None,
                guardrails=preflight,
            )
        tool_bindings = {item.name: item.sdk_tool for item in registration.tools}
        tools = tuple(tool_bindings[name] for name in request.requested_tools)
        try:
            sdk_result = await self._bridge.run(
                registration,
                request,
                output_type,
                context,
                tools,
            )
        except Exception as error:
            return self._result(
                registration,
                request,
                status=AgentRunStatus.FAILED,
                output=None,
                guardrails=GuardrailReport(outcome=GuardrailOutcome.PASSED),
                failure_reason=f"{type(error).__name__}: agent runtime failed",
            )
        guardrails = validate_agent_output(
            sdk_result.output,
            request,
            context,
            definition.policy,
            used_tools=sdk_result.used_tools,
        )
        if guardrails.outcome is GuardrailOutcome.REJECTED:
            return self._result(
                registration,
                request,
                status=AgentRunStatus.REJECTED,
                output=None,
                guardrails=guardrails,
                used_tools=sdk_result.used_tools,
                audit_output=sdk_result.output,
            )
        return self._result(
            registration,
            request,
            status=AgentRunStatus.ACCEPTED,
            output=sdk_result.output,
            guardrails=guardrails,
            used_tools=sdk_result.used_tools,
        )

    @staticmethod
    def _result[OutputT: AgentOutput](
        registration: OpenAIAgentRegistration,
        request: AgentRequest,
        *,
        status: AgentRunStatus,
        output: OutputT | None,
        guardrails: GuardrailReport,
        used_tools: tuple[str, ...] = (),
        failure_reason: str | None = None,
        audit_output: AgentOutput | None = None,
    ) -> AgentRunResult[OutputT]:
        definition = registration.definition
        return AgentRunResult[OutputT](
            run_id=request.run_id,
            status=status,
            output=output,
            failure_reason=failure_reason,
            guardrails=guardrails,
            audit=AgentRunAudit(
                runtime="openai-agents",
                runtime_version=version("openai-agents"),
                agent_id=definition.agent_id,
                model=definition.model,
                effort=definition.effort,
                prompt_version=definition.prompt_version,
                requested_tools=request.requested_tools,
                used_tools=used_tools,
                tracing_enabled=registration.tracing_enabled,
                request_hash=canonical_sha256(request),
                output_hash=(
                    canonical_sha256(audit_output or output)
                    if audit_output is not None or output is not None
                    else None
                ),
            ),
        )


def _used_tool_names(items: object) -> tuple[str, ...]:
    if not isinstance(items, (list, tuple)):
        return ()
    sequence = cast(list[object] | tuple[object, ...], items)
    names: list[str] = []
    for item in sequence:
        raw_item = getattr(item, "raw_item", None)
        name = getattr(raw_item, "name", None)
        if isinstance(name, str) and name not in names:
            names.append(name)
    return tuple(names)
