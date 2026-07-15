"""Acceptance tests for CR-001 immutable domain contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from deductra.domain.atoms import AssignmentAtom
from deductra.domain.constraints import DomainConstraint
from deductra.domain.puzzle import (
    Clue,
    DisplaySpec,
    ProvenanceBundle,
    PuzzleIdentity,
    PuzzleSpec,
)
from deductra.domain.schema import rendered_puzzle_spec_json_schema
from deductra.domain.serialization import canonical_json, canonical_sha256
from deductra.domain.values import Domain, DomainValue, Variable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def puzzle_spec() -> PuzzleSpec:
    """Build the smallest fully linked family-neutral puzzle specification."""
    return PuzzleSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:example",
            revision_id="deductra:revision:example:1",
            family_id="example",
            schema_version="1.0.0",
            title="One variable",
            source_kind="golden",
            created_at=datetime(2026, 7, 15, tzinfo=UTC),
        ),
        domains=(
            Domain(
                domain_id="deductra:domain:boolean",
                values=(
                    DomainValue(value_id="deductra:value:true", label="True"),
                    DomainValue(value_id="deductra:value:false", label="False"),
                ),
                ordered=False,
                metadata={"labels": ["logical", "binary"]},
            ),
        ),
        variables=(
            Variable(
                variable_id="deductra:variable:answer",
                label="Answer",
                domain_id="deductra:domain:boolean",
                role="answer",
            ),
        ),
        constraints=(
            DomainConstraint(
                constraint_id="deductra:constraint:answer-domain",
                label="Answer is true",
                allowed_value_ids=("deductra:value:true",),
                variable_id="deductra:variable:answer",
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:1",
                text="The answer is true.",
                constraint_ids=("deductra:constraint:answer-domain",),
                locale="en",
            ),
        ),
        givens=(
            AssignmentAtom(
                variable_id="deductra:variable:answer",
                value_id="deductra:value:true",
            ),
        ),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def test_schema_round_trip_is_lossless() -> None:
    """AC-CRM-001: validated JSON round-trips without semantic drift."""
    original = puzzle_spec()
    restored = PuzzleSpec.model_validate_json(original.model_dump_json())
    assert restored == original
    assert canonical_sha256(restored) == canonical_sha256(original)


def test_extra_fields_are_rejected_at_nested_boundaries() -> None:
    """AC-CRM-002: unknown fields cannot silently enter a domain object."""
    payload = puzzle_spec().model_dump(mode="json")
    payload["identity"]["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PuzzleSpec.model_validate(payload)


def test_specification_and_nested_metadata_are_immutable() -> None:
    """AC-CRM-003: a validated revision cannot be edited in place."""
    spec = puzzle_spec()
    with pytest.raises(ValidationError, match="Instance is frozen"):
        spec.identity.title = "Changed"
    with pytest.raises(TypeError):
        mutable_metadata = cast(dict[str, object], spec.domains[0].metadata)
        mutable_metadata["new"] = "value"
    labels = spec.domains[0].metadata["labels"]
    assert isinstance(labels, tuple)


def test_canonical_json_normalizes_unicode_and_key_order() -> None:
    composed = {"z": "é", "a": 1}
    decomposed = {"a": 1, "z": "e\u0301"}
    assert canonical_json(composed) == canonical_json(decomposed)


def test_checked_in_json_schema_is_current() -> None:
    schema_path = REPOSITORY_ROOT / "schemas" / "puzzle-spec-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == rendered_puzzle_spec_json_schema()
