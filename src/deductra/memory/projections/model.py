"""Immutable attempt, learning, novelty, and artifact projection models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from deductra.domain.base import DomainModel
from deductra.domain.ids import (
    ArtifactId,
    AttemptId,
    CandidateId,
    EventId,
    ProjectionStreamId,
    PuzzleId,
    PuzzleRevisionId,
    RuleId,
    UserId,
)
from deductra.domain.serialization import canonical_sha256
from deductra.generation.contracts import PuzzleFingerprints
from deductra.memory.projections.events import ProjectionEvent
from deductra.reasoning.events import Sha256Digest


class AttemptStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class RuleAttemptEvidence(DomainModel):
    rule_id: RuleId
    accepted_moves: int = Field(ge=0)
    rejected_moves: int = Field(ge=0)
    hints_revealed: int = Field(ge=0)
    explanations_viewed: int = Field(ge=0)
    evidence_event_ids: tuple[EventId, ...]


class AttemptProjection(DomainModel):
    """One attempt view derived entirely from its validated event stream."""

    attempt_id: AttemptId
    user_id: UserId
    puzzle_revision_id: PuzzleRevisionId
    stream_id: ProjectionStreamId
    status: AttemptStatus
    total_moves: int = Field(ge=0)
    accepted_moves: int = Field(ge=0)
    rejected_moves: int = Field(ge=0)
    hints_revealed: int = Field(ge=0)
    explanations_viewed: int = Field(ge=0)
    replays_viewed: int = Field(ge=0)
    self_assessment: int | None = Field(default=None, ge=1, le=5)
    rule_evidence: tuple[RuleAttemptEvidence, ...]
    source_event_ids: tuple[EventId, ...]
    source_head_hash: Sha256Digest
    projection_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_projection(self) -> AttemptProjection:
        if self.total_moves != self.accepted_moves + self.rejected_moves:
            raise ValueError("attempt move totals are inconsistent")
        if self.projection_hash != compute_projection_hash(self):
            raise ValueError("attempt projection hash is invalid")
        return self


class RuleLearningEvidence(DomainModel):
    """Descriptive evidence only; it is not a mastery score or diagnosis."""

    rule_id: RuleId
    attempts_observed: int = Field(ge=0)
    accepted_moves: int = Field(ge=0)
    rejected_moves: int = Field(ge=0)
    hints_revealed: int = Field(ge=0)
    explanations_viewed: int = Field(ge=0)
    evidence_event_ids: tuple[EventId, ...]


class LearningProjection(DomainModel):
    """Per-user descriptive aggregates rebuilt from attempt projections."""

    user_id: UserId
    attempts_observed: int = Field(ge=0)
    completed_attempts: int = Field(ge=0)
    abandoned_attempts: int = Field(ge=0)
    active_attempts: int = Field(ge=0)
    rule_evidence: tuple[RuleLearningEvidence, ...]
    source_stream_ids: tuple[ProjectionStreamId, ...]
    source_head_hashes: tuple[Sha256Digest, ...]
    projection_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_projection(self) -> LearningProjection:
        if self.attempts_observed != (
            self.completed_attempts + self.abandoned_attempts + self.active_attempts
        ):
            raise ValueError("learning attempt totals are inconsistent")
        if self.projection_hash != compute_projection_hash(self):
            raise ValueError("learning projection hash is invalid")
        return self


class NoveltyIndexEntry(DomainModel):
    puzzle_id: PuzzleId
    puzzle_revision_id: PuzzleRevisionId
    candidate_id: CandidateId
    fingerprints: PuzzleFingerprints
    evidence_ids: tuple[str, ...]
    source_event_id: EventId


class NoveltyIndex(DomainModel):
    """Accepted fingerprint entries; similarity algorithms remain out of scope."""

    entries: tuple[NoveltyIndexEntry, ...]
    source_stream_id: ProjectionStreamId | None
    source_head_hash: Sha256Digest | None
    projection_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_projection(self) -> NoveltyIndex:
        revision_ids = tuple(entry.puzzle_revision_id for entry in self.entries)
        if len(revision_ids) != len(set(revision_ids)):
            raise ValueError("novelty index revision identifiers must be unique")
        if self.projection_hash != compute_projection_hash(self):
            raise ValueError("novelty index hash is invalid")
        return self

    def canonical_matches(self, canonical_hash: str) -> tuple[PuzzleRevisionId, ...]:
        return tuple(
            entry.puzzle_revision_id
            for entry in self.entries
            if entry.fingerprints.canonical_hash == canonical_hash
        )


class ArtifactIndexEntry(DomainModel):
    artifact_id: ArtifactId
    puzzle_revision_id: PuzzleRevisionId
    artifact_kind: str
    media_type: str
    content_hash: Sha256Digest
    evidence_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    source_event_id: EventId
    superseded_by: ArtifactId | None = None


class ArtifactIndex(DomainModel):
    """Artifact metadata and provenance, never raw artifact content."""

    entries: tuple[ArtifactIndexEntry, ...]
    source_stream_id: ProjectionStreamId | None
    source_head_hash: Sha256Digest | None
    projection_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_projection(self) -> ArtifactIndex:
        artifact_ids = tuple(entry.artifact_id for entry in self.entries)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact index identifiers must be unique")
        if self.projection_hash != compute_projection_hash(self):
            raise ValueError("artifact index hash is invalid")
        return self


class MemoryProjectionBundle(DomainModel):
    """Complete disposable memory view rebuilt by one command."""

    projection_version: str
    attempts: tuple[AttemptProjection, ...]
    learning: tuple[LearningProjection, ...]
    novelty: NoveltyIndex
    artifacts: ArtifactIndex
    source_event_count: int = Field(ge=0)
    projection_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_projection(self) -> MemoryProjectionBundle:
        if self.projection_hash != compute_projection_hash(self):
            raise ValueError("memory projection bundle hash is invalid")
        return self


class MemoryProjectionContractDocument(DomainModel):
    """Versioned schema root for a rebuilt projection bundle."""

    source_events: tuple[ProjectionEvent, ...]
    bundle: MemoryProjectionBundle

    @model_validator(mode="after")
    def validate_rebuild_equivalence(self) -> MemoryProjectionContractDocument:
        from deductra.memory.projections.rebuild import rebuild_memory_projections

        rebuilt = rebuild_memory_projections(
            self.source_events,
            projection_version=self.bundle.projection_version,
        )
        if rebuilt != self.bundle:
            raise ValueError("projection bundle does not equal a clean event replay")
        return self


def compute_projection_hash(projection: DomainModel) -> str:
    return canonical_sha256(projection.model_dump(mode="json", exclude={"projection_hash"}))
