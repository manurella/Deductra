"""Deterministic policies for selecting human-rule applications."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from deductra.reasoning.rules import RuleApplicationCandidate


class ReasoningPolicy(StrEnum):
    """Supported family-neutral human deduction selection policies."""

    TEACHING_FIRST = "teaching_first"
    SHORTEST_TRACE = "shortest_trace"
    MAX_INFORMATION_GAIN = "max_information_gain"
    FAMILY_CANONICAL = "family_canonical"


def select_rule_application(
    candidates: Sequence[RuleApplicationCandidate],
    policy: ReasoningPolicy,
) -> RuleApplicationCandidate | None:
    """Select one candidate with a total deterministic ordering."""
    if not candidates:
        return None

    def stable_tail(item: RuleApplicationCandidate) -> tuple[int, str, str, str, str]:
        return (
            item.rule.technique_rank,
            item.rule.rule_id,
            item.rule.rule_version,
            item.tie_break_key,
            item.candidate_id,
        )

    def score(item: RuleApplicationCandidate) -> tuple[int | str, ...]:
        if policy is ReasoningPolicy.TEACHING_FIRST:
            return (item.pedagogical_cost, *stable_tail(item))
        if policy is ReasoningPolicy.SHORTEST_TRACE:
            return (-item.information_gain, item.pedagogical_cost, *stable_tail(item))
        if policy is ReasoningPolicy.MAX_INFORMATION_GAIN:
            return (-item.information_gain, *stable_tail(item))
        return stable_tail(item)

    return min(candidates, key=score)
