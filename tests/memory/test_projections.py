"""CR-008 replay-equivalence tests for disposable memory projections."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from deductra.domain.serialization import canonical_json
from deductra.generation import PuzzleFingerprints
from deductra.memory.projections import (
    PROJECTION_GENESIS_HASH,
    ArtifactRecorded,
    ArtifactSuperseded,
    AttemptCompleted,
    AttemptStarted,
    AttemptStatus,
    HintRevealed,
    MemoryProjectionContractDocument,
    MoveEvaluated,
    NoveltyEntryRecorded,
    ProjectionEvent,
    ProjectionRebuildError,
    ProjectionStreamKind,
    ReplayViewed,
    StepExplained,
    projection_event_chain_failures,
    rebuild_memory_projections,
    seal_projection_event,
)
from deductra.memory.projections.events import ProjectionEventPayload
from deductra.memory.projections.model import compute_projection_hash
from deductra.memory.projections.schema import rendered_memory_projection_json_schema

NOW = datetime(2026, 7, 16, 16, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


def fingerprints(prefix: str) -> PuzzleFingerprints:
    digits = (prefix * 64)[:64]
    return PuzzleFingerprints(
        content_hash=digits,
        canonical_hash=digits,
        solution_hash=digits,
        structure_hash=digits,
        trace_signature=digits,
        visual_structure_hash=digits,
    )


def stream(
    stream_id: str,
    kind: ProjectionStreamKind,
    payloads: tuple[ProjectionEventPayload, ...],
) -> tuple[ProjectionEvent, ...]:
    events: list[ProjectionEvent] = []
    previous_hash = PROJECTION_GENESIS_HASH
    for sequence_no, payload in enumerate(payloads):
        event = seal_projection_event(
            event_id=f"deductra:projection-event:{stream_id.rsplit(':', 1)[-1]}:{sequence_no}",
            stream_id=stream_id,
            stream_kind=kind,
            sequence_no=sequence_no,
            schema_version="1.0.0",
            occurred_at=NOW + timedelta(seconds=sequence_no),
            previous_event_hash=previous_hash,
            payload=payload,
        )
        events.append(event)
        previous_hash = event.event_hash
    return tuple(events)


def attempt_stream() -> tuple[ProjectionEvent, ...]:
    return stream(
        "deductra:projection-stream:attempt-1",
        ProjectionStreamKind.ATTEMPT,
        (
            AttemptStarted(
                attempt_id="deductra:attempt:1",
                user_id="deductra:user:1",
                puzzle_revision_id="deductra:revision:1",
            ),
            MoveEvaluated(
                attempt_id="deductra:attempt:1",
                outcome="accepted",
                rule_id="deductra:rule:single",
                duration_ms=100,
            ),
            MoveEvaluated(
                attempt_id="deductra:attempt:1",
                outcome="rejected",
                rule_id="deductra:rule:single",
                duration_ms=200,
            ),
            HintRevealed(
                attempt_id="deductra:attempt:1",
                rule_id="deductra:rule:single",
            ),
            StepExplained(
                attempt_id="deductra:attempt:1",
                rule_id="deductra:rule:single",
            ),
            AttemptCompleted(attempt_id="deductra:attempt:1"),
        ),
    )


def novelty_stream() -> tuple[ProjectionEvent, ...]:
    return stream(
        "deductra:projection-stream:novelty",
        ProjectionStreamKind.NOVELTY,
        (
            NoveltyEntryRecorded(
                puzzle_id="deductra:puzzle:1",
                puzzle_revision_id="deductra:revision:1",
                candidate_id="deductra:candidate:1",
                fingerprints=fingerprints("1"),
                evidence_ids=("deductra:evidence:novelty:1",),
            ),
            NoveltyEntryRecorded(
                puzzle_id="deductra:puzzle:2",
                puzzle_revision_id="deductra:revision:2",
                candidate_id="deductra:candidate:2",
                fingerprints=fingerprints("2"),
                evidence_ids=("deductra:evidence:novelty:2",),
            ),
        ),
    )


def artifact_stream() -> tuple[ProjectionEvent, ...]:
    return stream(
        "deductra:projection-stream:artifact",
        ProjectionStreamKind.ARTIFACT,
        (
            ArtifactRecorded(
                artifact_id="deductra:artifact:old",
                puzzle_revision_id="deductra:revision:1",
                artifact_kind="export",
                media_type="application/json",
                content_hash="3" * 64,
                evidence_ids=("deductra:event:evidence",),
                provenance_ids=("deductra:provenance:export",),
            ),
            ArtifactRecorded(
                artifact_id="deductra:artifact:new",
                puzzle_revision_id="deductra:revision:1",
                artifact_kind="export",
                media_type="application/json",
                content_hash="4" * 64,
                evidence_ids=("deductra:event:evidence",),
                provenance_ids=("deductra:provenance:export",),
            ),
            ArtifactSuperseded(
                artifact_id="deductra:artifact:old",
                replacement_artifact_id="deductra:artifact:new",
            ),
        ),
    )


def all_events() -> tuple[ProjectionEvent, ...]:
    return (*attempt_stream(), *novelty_stream(), *artifact_stream())


def test_rebuild_is_exact_and_independent_of_input_enumeration_order() -> None:
    events = all_events()
    first = rebuild_memory_projections(events)
    second = rebuild_memory_projections(reversed(events))
    assert first == second
    assert canonical_json(first) == canonical_json(second)
    assert first.source_event_count == len(events)


def test_attempt_and_learning_views_are_evidence_bounded() -> None:
    rebuilt = rebuild_memory_projections(all_events())
    attempt = rebuilt.attempts[0]
    learning = rebuilt.learning[0]
    assert attempt.status is AttemptStatus.COMPLETED
    assert (attempt.total_moves, attempt.accepted_moves, attempt.rejected_moves) == (2, 1, 1)
    assert (attempt.hints_revealed, attempt.explanations_viewed) == (1, 1)
    assert learning.attempts_observed == 1
    evidence = learning.rule_evidence[0]
    assert (evidence.accepted_moves, evidence.rejected_moves) == (1, 1)
    serialized = canonical_json(learning)
    assert "mastery" not in serialized
    assert "confidence" not in serialized


def test_novelty_and_artifact_indexes_are_queryable_metadata_views() -> None:
    rebuilt = rebuild_memory_projections(all_events())
    assert rebuilt.novelty.canonical_matches("1" * 64) == ("deductra:revision:1",)
    artifacts = {entry.artifact_id: entry for entry in rebuilt.artifacts.entries}
    assert artifacts["deductra:artifact:old"].superseded_by == "deductra:artifact:new"
    assert '"content":' not in canonical_json(rebuilt.artifacts)


def test_projection_bundle_round_trips_through_canonical_json() -> None:
    events = all_events()
    document = MemoryProjectionContractDocument(
        source_events=events,
        bundle=rebuild_memory_projections(events),
    )
    encoded = canonical_json(document)
    assert MemoryProjectionContractDocument.model_validate_json(encoded) == document


def test_contract_document_rejects_a_bundle_that_drifted_from_replay() -> None:
    events = all_events()
    rebuilt = rebuild_memory_projections(events)
    unsigned = rebuilt.model_copy(update={"source_event_count": rebuilt.source_event_count + 1})
    drifted = unsigned.model_copy(update={"projection_hash": compute_projection_hash(unsigned)})
    with pytest.raises(ValueError, match="clean event replay"):
        MemoryProjectionContractDocument(source_events=events, bundle=drifted)


def test_tampered_event_prevents_every_projection_rebuild() -> None:
    events = list(all_events())
    events[1] = events[1].model_copy(
        update={
            "payload": MoveEvaluated(
                attempt_id="deductra:attempt:1",
                outcome="rejected",
                rule_id="deductra:rule:single",
                duration_ms=100,
            )
        }
    )
    assert projection_event_chain_failures(tuple(events[:6])) == (
        "deductra:projection-event:attempt-1:1:event_hash",
    )
    with pytest.raises(ProjectionRebuildError, match="invalid"):
        rebuild_memory_projections(events)


def test_attempt_events_after_completion_are_rejected() -> None:
    events = attempt_stream()
    replay = seal_projection_event(
        event_id="deductra:projection-event:attempt-1:6",
        stream_id=events[0].stream_id,
        stream_kind=ProjectionStreamKind.ATTEMPT,
        sequence_no=6,
        schema_version="1.0.0",
        occurred_at=NOW + timedelta(seconds=6),
        previous_event_hash=events[-1].event_hash,
        payload=ReplayViewed(attempt_id="deductra:attempt:1"),
    )
    with pytest.raises(ProjectionRebuildError, match="terminal"):
        rebuild_memory_projections((*events, replay))


def test_checked_in_memory_projection_schema_is_current() -> None:
    path = ROOT / "schemas" / "memory-projections-v1.schema.json"
    assert path.read_text(encoding="utf-8") == rendered_memory_projection_json_schema()
