"""Ports for deterministic evidence providers used by future generators."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from deductra.domain.puzzle import PuzzleSpec
from deductra.generation.contracts import (
    DifficultyEvidence,
    GenerationRequest,
    NoveltyEvidence,
    PuzzleFingerprints,
    UniquenessEvidence,
)
from deductra.reasoning.engine import HumanSolveTrace


@runtime_checkable
class UniquenessEvaluator(Protocol):
    """Prove zero, one, multiple, or unknown solutions without accepting unknown."""

    def evaluate_uniqueness(
        self,
        puzzle: PuzzleSpec,
        *,
        time_budget_ms: int,
    ) -> UniquenessEvidence: ...


@runtime_checkable
class DifficultyEvaluator(Protocol):
    """Derive family-relative evidence from a canonical human trace."""

    def evaluate_difficulty(
        self,
        request: GenerationRequest,
        puzzle: PuzzleSpec,
        trace: HumanSolveTrace,
    ) -> DifficultyEvidence: ...


@runtime_checkable
class FingerprintEvaluator(Protocol):
    """Compute the stable fingerprint set for an immutable candidate."""

    def fingerprint(self, puzzle: PuzzleSpec, trace: HumanSolveTrace) -> PuzzleFingerprints: ...


@runtime_checkable
class NoveltyEvaluator(Protocol):
    """Compare fingerprints conservatively against an external novelty index."""

    def evaluate_novelty(
        self,
        policy_id: str,
        fingerprints: PuzzleFingerprints,
    ) -> NoveltyEvidence: ...
