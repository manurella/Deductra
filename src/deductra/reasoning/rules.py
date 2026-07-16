"""Family-neutral human reasoning rule contracts and deterministic discovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Protocol, Self, cast, runtime_checkable

from pydantic import Field, JsonValue, field_serializer, field_validator, model_validator

from deductra.domain.atoms import Atom
from deductra.domain.base import DomainModel, freeze_json, thaw_json
from deductra.domain.ids import ConstraintId, RuleCandidateId, RuleId, VariableId
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_json
from deductra.reasoning.events import Sha256Digest
from deductra.reasoning.state import PuzzleState


class RuleContractError(ValueError):
    """A rule or its proposed application violates the human-rule boundary."""


class RuleReference(DomainModel):
    """Stable identity and teaching rank for one versioned human rule."""

    rule_id: RuleId
    rule_version: str
    family_scope: tuple[str, ...] = ()
    title: str
    technique_rank: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if len(self.family_scope) != len(set(self.family_scope)):
            raise ValueError("family_scope entries must be unique")
        return self


class RuleApplicationCandidate(DomainModel):
    """One deterministic location where a human rule claims it can apply."""

    candidate_id: RuleCandidateId
    rule: RuleReference
    source_state_hash: Sha256Digest
    premises: tuple[Atom, ...] = ()
    affected_variables: tuple[VariableId, ...]
    supporting_constraints: tuple[ConstraintId, ...] = ()
    information_gain: Annotated[int, Field(ge=0)] = 0
    pedagogical_cost: Annotated[int, Field(ge=0)] = 0
    tie_break_key: str

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        for label, values in (
            ("premises", tuple(canonical_json(item) for item in self.premises)),
            ("affected_variables", self.affected_variables),
            ("supporting_constraints", self.supporting_constraints),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if not self.affected_variables:
            raise ValueError("a rule candidate must affect at least one variable")
        return self


class ProposedDeduction(DomainModel):
    """Non-authoritative deduction proposed by one human reasoning rule."""

    candidate_id: RuleCandidateId
    source_state_hash: Sha256Digest
    rule: RuleReference
    premises: tuple[Atom, ...] = ()
    conclusions: tuple[Atom, ...]
    affected_variables: tuple[VariableId, ...]
    supporting_constraints: tuple[ConstraintId, ...] = ()
    explanation_parameters: Mapping[str, JsonValue] = Field(default_factory=dict)

    @field_validator("explanation_parameters", mode="after")
    @classmethod
    def freeze_explanation_parameters(
        cls, value: Mapping[str, JsonValue]
    ) -> Mapping[str, JsonValue]:
        return cast(Mapping[str, JsonValue], freeze_json(value))

    @field_serializer("explanation_parameters")
    def serialize_explanation_parameters(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        return cast(dict[str, Any], thaw_json(value))

    @model_validator(mode="after")
    def validate_deduction(self) -> Self:
        if not self.conclusions:
            raise ValueError("a proposed deduction requires a conclusion")
        for label, values in (
            ("premises", tuple(canonical_json(item) for item in self.premises)),
            ("conclusions", tuple(canonical_json(item) for item in self.conclusions)),
            ("affected_variables", self.affected_variables),
            ("supporting_constraints", self.supporting_constraints),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        return self


@runtime_checkable
class ReasoningRule(Protocol):
    """Port implemented by deterministic, family-specific human rules."""

    reference: RuleReference

    def find_applications(
        self, puzzle: PuzzleSpec, state: PuzzleState
    ) -> Sequence[RuleApplicationCandidate]: ...

    def apply(
        self, candidate: RuleApplicationCandidate, state: PuzzleState
    ) -> ProposedDeduction: ...


def discover_rule_applications(
    puzzle: PuzzleSpec,
    state: PuzzleState,
    rules: Sequence[ReasoningRule],
) -> tuple[RuleApplicationCandidate, ...]:
    """Discover and canonically order every in-scope application."""
    if state.puzzle_revision_id != puzzle.identity.revision_id:
        raise RuleContractError("rule discovery state does not match the puzzle revision")
    identities = tuple((rule.reference.rule_id, rule.reference.rule_version) for rule in rules)
    if len(identities) != len(set(identities)):
        raise RuleContractError("reasoning rule identities must be unique")

    discovered: list[RuleApplicationCandidate] = []
    for rule in sorted(rules, key=lambda item: canonical_json(item.reference)):
        scope = rule.reference.family_scope
        if scope and puzzle.identity.family_id not in scope:
            continue
        for candidate in rule.find_applications(puzzle, state):
            if candidate.rule != rule.reference:
                raise RuleContractError("candidate rule reference does not match its producer")
            if candidate.source_state_hash != state.state_hash:
                raise RuleContractError("candidate source state is stale")
            discovered.append(candidate)

    candidate_ids = tuple(item.candidate_id for item in discovered)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise RuleContractError("candidate identifiers must be unique within a state")
    return tuple(
        sorted(
            discovered,
            key=lambda item: (
                item.rule.technique_rank,
                item.rule.rule_id,
                item.rule.rule_version,
                item.tie_break_key,
                item.candidate_id,
            ),
        )
    )
