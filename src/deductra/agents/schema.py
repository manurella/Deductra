"""Canonical JSON Schema export for the agent boundary."""

from __future__ import annotations

import json
from typing import Any

from deductra.agents.contracts import (
    AgentContextView,
    AgentOutput,
    AgentPolicy,
    AgentRequest,
    AgentRunResult,
)
from deductra.domain.base import DomainModel


class AgentBoundaryContractDocument(DomainModel):
    request: AgentRequest
    context: AgentContextView
    policy: AgentPolicy
    result: AgentRunResult[AgentOutput]


def agent_boundary_json_schema() -> dict[str, Any]:
    return AgentBoundaryContractDocument.model_json_schema()


def rendered_agent_boundary_json_schema() -> str:
    return json.dumps(agent_boundary_json_schema(), indent=2, sort_keys=True) + "\n"
