from __future__ import annotations

import asyncio
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

import pytest

from deductra.agents.contracts import (
    AgentClaim,
    AgentClaimKind,
    AgentClaimMethod,
    AgentContextView,
    AgentOutput,
    AgentRunStatus,
    GuardrailCode,
)
from deductra.agents.openai_runtime import (
    DefaultOpenAISdkBridge,
    OpenAIAgentDefinition,
    OpenAIAgentRegistration,
    OpenAIAgentsRuntime,
    OpenAISdkBridge,
    SdkRunResult,
)
from deductra.agents.runtime import AgentRuntime, DisabledAgentRuntime

from .conftest import EVIDENCE_ID, make_context, make_policy, make_request


def accepted_output() -> AgentOutput:
    return AgentOutput(
        claims=(
            AgentClaim(
                claim_id="claim:grounded:1",
                kind=AgentClaimKind.FACTUAL,
                method=AgentClaimMethod.DETERMINISTIC_EVIDENCE,
                text="A grounded deterministic fact.",
                evidence_ids=(EVIDENCE_ID,),
            ),
        ),
    )


@dataclass
class FakeBridge(OpenAISdkBridge):
    output: AgentOutput
    used_tools: tuple[str, ...] = ()
    calls: int = 0

    async def run[OutputT: AgentOutput](
        self,
        registration: OpenAIAgentRegistration,
        request: object,
        output_type: type[OutputT],
        context: object,
        tools: tuple[object, ...],
    ) -> SdkRunResult[OutputT]:
        del registration, request, context, tools
        self.calls += 1
        return SdkRunResult(
            output=output_type.model_validate(self.output),
            used_tools=self.used_tools,
        )


def registration() -> OpenAIAgentRegistration:
    return OpenAIAgentRegistration(
        definition=OpenAIAgentDefinition(
            agent_id="agent:auditor",
            name="Auditor",
            instructions="fixture",
            model="test-model",
            effort="low",
            prompt_version="1.0.0",
            policy=make_policy(tools=()),
        ),
    )


def test_disabled_runtime_satisfies_port_without_remote_execution() -> None:
    runtime = DisabledAgentRuntime()
    assert isinstance(runtime, AgentRuntime)
    result = asyncio.run(
        runtime.run_typed(
            "agent:auditor",
            make_request(),
            AgentOutput,
            make_context(),
        )
    )
    assert result.status is AgentRunStatus.DISABLED
    assert result.output is None
    assert result.audit.tracing_enabled is False


def test_openai_adapter_accepts_only_post_guardrail_output() -> None:
    bridge = FakeBridge(accepted_output())
    runtime = OpenAIAgentsRuntime((registration(),), bridge=bridge)
    result = asyncio.run(
        runtime.run_typed(
            "agent:auditor",
            make_request(),
            AgentOutput,
            make_context(),
        )
    )
    assert result.status is AgentRunStatus.ACCEPTED
    assert result.output == accepted_output()
    assert result.audit.model == "test-model"
    assert result.audit.prompt_version == "1.0.0"
    assert bridge.calls == 1


def test_preflight_rejection_does_not_invoke_sdk() -> None:
    bridge = FakeBridge(accepted_output())
    runtime = OpenAIAgentsRuntime((registration(),), bridge=bridge)
    result = asyncio.run(
        runtime.run_typed(
            "agent:auditor",
            make_request(tools=("unrestricted_storage",)),
            AgentOutput,
            make_context(),
        )
    )
    assert result.status is AgentRunStatus.REJECTED
    assert result.output is None
    assert {item.code for item in result.guardrails.findings} == {GuardrailCode.TOOL_NOT_ALLOWED}
    assert bridge.calls == 0


def test_postflight_rejection_hides_untrusted_output() -> None:
    bridge = FakeBridge(
        AgentOutput(
            claims=(
                AgentClaim(
                    claim_id="claim:unknown",
                    kind=AgentClaimKind.FACTUAL,
                    method=AgentClaimMethod.DETERMINISTIC_EVIDENCE,
                    text="Unknown claim.",
                    evidence_ids=("evidence:unknown",),
                ),
            ),
        )
    )
    runtime = OpenAIAgentsRuntime((registration(),), bridge=bridge)
    result = asyncio.run(
        runtime.run_typed(
            "agent:auditor",
            make_request(),
            AgentOutput,
            make_context(),
        )
    )
    assert result.status is AgentRunStatus.REJECTED
    assert result.output is None
    assert result.audit.output_hash is not None
    assert GuardrailCode.UNKNOWN_EVIDENCE in {item.code for item in result.guardrails.findings}


@dataclass(frozen=True)
class _SdkResult:
    final_output: AgentOutput
    new_items: tuple[object, ...] = ()


class _ReasoningView(Protocol):
    effort: str | None


class _ModelSettingsView(Protocol):
    reasoning: _ReasoningView | None


class _ConfiguredAgentView(Protocol):
    output_type: object
    model: object
    model_settings: _ModelSettingsView


class _RunConfigView(Protocol):
    tracing_disabled: bool
    trace_include_sensitive_data: bool


def test_default_bridge_configures_structured_output_and_private_tracing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run(
        agent: object,
        model_input: str,
        *,
        context: AgentContextView,
        run_config: object,
    ) -> _SdkResult:
        captured["agent"] = agent
        captured["input"] = model_input
        captured["context"] = context
        captured["run_config"] = run_config
        return _SdkResult(final_output=accepted_output())

    sdk = import_module("agents")
    monkeypatch.setattr(sdk.Runner, "run", fake_run)
    bridge_result = asyncio.run(
        DefaultOpenAISdkBridge().run(
            registration(),
            make_request(),
            AgentOutput,
            make_context(),
            (),
        )
    )
    configured_agent = cast(_ConfiguredAgentView, captured["agent"])
    run_config = cast(_RunConfigView, captured["run_config"])
    assert bridge_result.output == accepted_output()
    assert configured_agent.output_type is AgentOutput
    assert configured_agent.model == "test-model"
    assert configured_agent.model_settings.reasoning is not None
    assert configured_agent.model_settings.reasoning.effort == "low"
    assert run_config.tracing_disabled is True
    assert run_config.trace_include_sensitive_data is False
