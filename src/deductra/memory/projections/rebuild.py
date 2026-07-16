"""Pure rebuild commands for every CR-008 memory projection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from deductra.domain.base import DomainModel
from deductra.domain.ids import ArtifactId, EventId, RuleId, UserId
from deductra.domain.serialization import canonical_sha256
from deductra.memory.projections.events import (
    ArtifactRecorded,
    ArtifactRemoved,
    ArtifactSuperseded,
    AttemptAbandoned,
    AttemptCompleted,
    AttemptStarted,
    HintRevealed,
    MoveEvaluated,
    NoveltyEntryRecorded,
    NoveltyEntryRemoved,
    ProjectionEvent,
    ProjectionStreamKind,
    ReplayViewed,
    SelfAssessmentRecorded,
    StepExplained,
    projection_event_chain_failures,
)
from deductra.memory.projections.model import (
    ArtifactIndex,
    ArtifactIndexEntry,
    AttemptProjection,
    AttemptStatus,
    LearningProjection,
    MemoryProjectionBundle,
    NoveltyIndex,
    NoveltyIndexEntry,
    RuleAttemptEvidence,
    RuleLearningEvidence,
)


class ProjectionRebuildError(ValueError):
    """Raised when source events cannot produce one unambiguous projection."""


@dataclass
class _RuleCounts:
    accepted: int = 0
    rejected: int = 0
    hints: int = 0
    explanations: int = 0
    event_ids: list[EventId] | None = None

    def add_event(self, event_id: EventId) -> None:
        if self.event_ids is None:
            self.event_ids = []
        self.event_ids.append(event_id)


def _validated_streams(
    events: Iterable[ProjectionEvent],
) -> dict[str, tuple[ProjectionEvent, ...]]:
    grouped: dict[str, list[ProjectionEvent]] = defaultdict(list)
    event_ids: set[EventId] = set()
    for event in events:
        if event.event_id in event_ids:
            raise ProjectionRebuildError(f"duplicate projection event: {event.event_id}")
        event_ids.add(event.event_id)
        grouped[event.stream_id].append(event)

    streams: dict[str, tuple[ProjectionEvent, ...]] = {}
    for stream_id, unordered in grouped.items():
        ordered = tuple(sorted(unordered, key=lambda item: item.sequence_no))
        failures = projection_event_chain_failures(ordered)
        if failures:
            raise ProjectionRebuildError(
                f"projection stream {stream_id} is invalid: {list(failures)}"
            )
        streams[stream_id] = ordered
    return streams


def _sealed[ProjectionT: DomainModel](
    model_type: type[ProjectionT], **values: object
) -> ProjectionT:
    return model_type.model_validate({**values, "projection_hash": canonical_sha256(values)})


def rebuild_attempt_projection(events: tuple[ProjectionEvent, ...]) -> AttemptProjection:
    if not events or events[0].stream_kind is not ProjectionStreamKind.ATTEMPT:
        raise ProjectionRebuildError("attempt projection requires one non-empty attempt stream")
    failures = projection_event_chain_failures(events)
    if failures:
        raise ProjectionRebuildError(f"attempt stream is invalid: {list(failures)}")
    first = events[0].payload
    if not isinstance(first, AttemptStarted):
        raise ProjectionRebuildError("attempt stream must begin with attempt_started")

    status = AttemptStatus.ACTIVE
    accepted = rejected = hints = explanations = replays = 0
    self_assessment: int | None = None
    terminal = False
    rules: dict[RuleId, _RuleCounts] = defaultdict(_RuleCounts)

    for event in events[1:]:
        payload = event.payload
        attempt_id = getattr(payload, "attempt_id", None)
        if attempt_id != first.attempt_id:
            raise ProjectionRebuildError("attempt payload identifier changed within its stream")
        if terminal:
            raise ProjectionRebuildError("attempt stream contains events after its terminal event")
        if isinstance(payload, MoveEvaluated):
            if payload.outcome == "accepted":
                accepted += 1
            else:
                rejected += 1
            if payload.rule_id is not None:
                counts = rules[payload.rule_id]
                if payload.outcome == "accepted":
                    counts.accepted += 1
                else:
                    counts.rejected += 1
                counts.add_event(event.event_id)
        elif isinstance(payload, HintRevealed):
            hints += 1
            if payload.rule_id is not None:
                rules[payload.rule_id].hints += 1
                rules[payload.rule_id].add_event(event.event_id)
        elif isinstance(payload, StepExplained):
            explanations += 1
            rules[payload.rule_id].explanations += 1
            rules[payload.rule_id].add_event(event.event_id)
        elif isinstance(payload, ReplayViewed):
            replays += 1
        elif isinstance(payload, SelfAssessmentRecorded):
            self_assessment = payload.rating
        elif isinstance(payload, AttemptCompleted):
            status = AttemptStatus.COMPLETED
            terminal = True
        elif isinstance(payload, AttemptAbandoned):
            status = AttemptStatus.ABANDONED
            terminal = True
        else:
            raise ProjectionRebuildError("non-attempt payload appeared in an attempt stream")

    rule_evidence = tuple(
        RuleAttemptEvidence(
            rule_id=rule_id,
            accepted_moves=counts.accepted,
            rejected_moves=counts.rejected,
            hints_revealed=counts.hints,
            explanations_viewed=counts.explanations,
            evidence_event_ids=tuple(counts.event_ids or ()),
        )
        for rule_id, counts in sorted(rules.items())
    )
    return _sealed(
        AttemptProjection,
        attempt_id=first.attempt_id,
        user_id=first.user_id,
        puzzle_revision_id=first.puzzle_revision_id,
        stream_id=events[0].stream_id,
        status=status,
        total_moves=accepted + rejected,
        accepted_moves=accepted,
        rejected_moves=rejected,
        hints_revealed=hints,
        explanations_viewed=explanations,
        replays_viewed=replays,
        self_assessment=self_assessment,
        rule_evidence=rule_evidence,
        source_event_ids=tuple(event.event_id for event in events),
        source_head_hash=events[-1].event_hash,
    )


def rebuild_learning_projections(
    attempts: tuple[AttemptProjection, ...],
) -> tuple[LearningProjection, ...]:
    by_user: dict[UserId, list[AttemptProjection]] = defaultdict(list)
    for attempt in attempts:
        by_user[attempt.user_id].append(attempt)

    projections: list[LearningProjection] = []
    for user_id, unordered in sorted(by_user.items()):
        observed = tuple(sorted(unordered, key=lambda item: item.attempt_id))
        rules: dict[RuleId, _RuleCounts] = defaultdict(_RuleCounts)
        rule_attempts: dict[RuleId, int] = defaultdict(int)
        for attempt in observed:
            for evidence in attempt.rule_evidence:
                rule_attempts[evidence.rule_id] += 1
                counts = rules[evidence.rule_id]
                counts.accepted += evidence.accepted_moves
                counts.rejected += evidence.rejected_moves
                counts.hints += evidence.hints_revealed
                counts.explanations += evidence.explanations_viewed
                for event_id in evidence.evidence_event_ids:
                    counts.add_event(event_id)
        rule_evidence = tuple(
            RuleLearningEvidence(
                rule_id=rule_id,
                attempts_observed=rule_attempts[rule_id],
                accepted_moves=counts.accepted,
                rejected_moves=counts.rejected,
                hints_revealed=counts.hints,
                explanations_viewed=counts.explanations,
                evidence_event_ids=tuple(sorted(set(counts.event_ids or ()))),
            )
            for rule_id, counts in sorted(rules.items())
        )
        projections.append(
            _sealed(
                LearningProjection,
                user_id=user_id,
                attempts_observed=len(observed),
                completed_attempts=sum(item.status is AttemptStatus.COMPLETED for item in observed),
                abandoned_attempts=sum(item.status is AttemptStatus.ABANDONED for item in observed),
                active_attempts=sum(item.status is AttemptStatus.ACTIVE for item in observed),
                rule_evidence=rule_evidence,
                source_stream_ids=tuple(item.stream_id for item in observed),
                source_head_hashes=tuple(item.source_head_hash for item in observed),
            )
        )
    return tuple(projections)


def _single_stream(
    streams: dict[str, tuple[ProjectionEvent, ...]], kind: ProjectionStreamKind
) -> tuple[ProjectionEvent, ...]:
    matching = tuple(stream for stream in streams.values() if stream[0].stream_kind is kind)
    if len(matching) > 1:
        raise ProjectionRebuildError(f"{kind.value} index requires one canonical source stream")
    return matching[0] if matching else ()


def rebuild_novelty_index(events: tuple[ProjectionEvent, ...]) -> NoveltyIndex:
    entries: dict[str, NoveltyIndexEntry] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, NoveltyEntryRecorded):
            if payload.puzzle_revision_id in entries:
                raise ProjectionRebuildError("novelty revision was recorded more than once")
            entries[payload.puzzle_revision_id] = NoveltyIndexEntry(
                puzzle_id=payload.puzzle_id,
                puzzle_revision_id=payload.puzzle_revision_id,
                candidate_id=payload.candidate_id,
                fingerprints=payload.fingerprints,
                evidence_ids=payload.evidence_ids,
                source_event_id=event.event_id,
            )
        elif isinstance(payload, NoveltyEntryRemoved):
            if entries.pop(payload.puzzle_revision_id, None) is None:
                raise ProjectionRebuildError("novelty removal references an unknown revision")
        else:
            raise ProjectionRebuildError("non-novelty payload appeared in the novelty stream")
    return _sealed(
        NoveltyIndex,
        entries=tuple(sorted(entries.values(), key=lambda item: item.puzzle_revision_id)),
        source_stream_id=events[0].stream_id if events else None,
        source_head_hash=events[-1].event_hash if events else None,
    )


def rebuild_artifact_index(events: tuple[ProjectionEvent, ...]) -> ArtifactIndex:
    entries: dict[ArtifactId, ArtifactIndexEntry] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, ArtifactRecorded):
            if payload.artifact_id in entries:
                raise ProjectionRebuildError("artifact was recorded more than once")
            entries[payload.artifact_id] = ArtifactIndexEntry(
                artifact_id=payload.artifact_id,
                puzzle_revision_id=payload.puzzle_revision_id,
                artifact_kind=payload.artifact_kind,
                media_type=payload.media_type,
                content_hash=payload.content_hash,
                evidence_ids=payload.evidence_ids,
                provenance_ids=payload.provenance_ids,
                source_event_id=event.event_id,
            )
        elif isinstance(payload, ArtifactSuperseded):
            current = entries.get(payload.artifact_id)
            if current is None or payload.replacement_artifact_id not in entries:
                raise ProjectionRebuildError("artifact supersession must resolve both artifacts")
            if payload.artifact_id == payload.replacement_artifact_id:
                raise ProjectionRebuildError("an artifact cannot supersede itself")
            entries[payload.artifact_id] = current.model_copy(
                update={"superseded_by": payload.replacement_artifact_id}
            )
        elif isinstance(payload, ArtifactRemoved):
            if entries.pop(payload.artifact_id, None) is None:
                raise ProjectionRebuildError("artifact removal references an unknown artifact")
        else:
            raise ProjectionRebuildError("non-artifact payload appeared in the artifact stream")
    return _sealed(
        ArtifactIndex,
        entries=tuple(sorted(entries.values(), key=lambda item: item.artifact_id)),
        source_stream_id=events[0].stream_id if events else None,
        source_head_hash=events[-1].event_hash if events else None,
    )


def rebuild_memory_projections(
    events: Iterable[ProjectionEvent],
    *,
    projection_version: str = "1.0.0",
) -> MemoryProjectionBundle:
    """Rebuild every disposable view from validated events in one pure command."""
    source_events = tuple(events)
    streams = _validated_streams(source_events)
    attempts = tuple(
        sorted(
            (
                rebuild_attempt_projection(stream)
                for stream in streams.values()
                if stream[0].stream_kind is ProjectionStreamKind.ATTEMPT
            ),
            key=lambda item: item.attempt_id,
        )
    )
    learning = rebuild_learning_projections(attempts)
    novelty = rebuild_novelty_index(_single_stream(streams, ProjectionStreamKind.NOVELTY))
    artifacts = rebuild_artifact_index(_single_stream(streams, ProjectionStreamKind.ARTIFACT))
    return _sealed(
        MemoryProjectionBundle,
        projection_version=projection_version,
        attempts=attempts,
        learning=learning,
        novelty=novelty,
        artifacts=artifacts,
        source_event_count=len(source_events),
    )
