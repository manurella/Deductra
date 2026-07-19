"""Acceptance tests for the FAM-LG-001 Logic Grid specification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    Add,
    Constant,
    Equal,
    LessThan,
    Subtract,
    VariableReference,
    Xor,
)
from deductra.domain.puzzle import Clue, DisplaySpec, ProvenanceBundle, PuzzleIdentity
from deductra.domain.serialization import canonical_sha256
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_grid import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridCategory,
    LogicGridSpec,
    logic_grid_spec_json_schema,
    rendered_logic_grid_spec_json_schema,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def logic_grid_spec() -> LogicGridSpec:
    """Build a three-by-three specification fixture that is not Golden content."""
    category_data = (
        ("people", "People", ("Ada", "Ben", "Cleo"), False),
        ("exhibits", "Exhibits", ("Kite", "Loom", "Mask"), False),
        ("days", "Days", ("Day 1", "Day 2", "Day 3"), True),
    )
    domains = tuple(
        Domain(
            domain_id=f"deductra:domain:logic-grid:{category_id}",
            values=tuple(
                DomainValue(
                    value_id=f"deductra:value:logic-grid:{category_id}:{index}",
                    label=label,
                    ordinal=index if ordered else None,
                    numeric_value=index if ordered else None,
                )
                for index, label in enumerate(labels, start=1)
            ),
            ordered=ordered,
            distinct_by_default=True,
        )
        for category_id, _, labels, ordered in category_data
    )
    anchor_domain = domains[-1]
    categories = tuple(
        LogicGridCategory(
            category_id=f"deductra:category:logic-grid:{category_id}",
            label=category_label,
            domain_id=domain.domain_id,
            variable_ids=tuple(
                f"deductra:variable:logic-grid:{category_id}:{index}" for index in range(1, 4)
            ),
        )
        for (category_id, category_label, _, _), domain in zip(
            category_data,
            domains,
            strict=True,
        )
    )
    variables = tuple(
        Variable(
            variable_id=variable_id,
            label=value.label,
            domain_id=anchor_domain.domain_id,
            role="entity_assignment",
        )
        for category, domain in zip(categories, domains, strict=True)
        for variable_id, value in zip(category.variable_ids, domain.values, strict=True)
    )
    clue_constraint_id = "deductra:constraint:logic-grid:ada-with-loom"
    return LogicGridSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:logic-grid-spec-fixture",
            revision_id="deductra:revision:logic-grid-spec-fixture:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title="Logic Grid specification fixture",
            source_kind="user",
            created_at=datetime(2026, 7, 19, tzinfo=UTC),
        ),
        domains=domains,
        variables=variables,
        constraints=(
            *(
                AllDifferentConstraint(
                    constraint_id=f"deductra:constraint:logic-grid:{category.category_id}:bijection",
                    label=f"{category.label} items occupy different rows",
                    variable_ids=category.variable_ids,
                )
                for category in categories
            ),
            ArithmeticConstraint(
                constraint_id=clue_constraint_id,
                label="Ada was associated with the Loom",
                source_clue_id="deductra:clue:logic-grid:ada-with-loom",
                expression=Equal(
                    left=VariableReference(variable_id=categories[0].variable_ids[0]),
                    right=VariableReference(variable_id=categories[1].variable_ids[1]),
                ),
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:logic-grid:ada-with-loom",
                text="Ada was associated with the Loom.",
                constraint_ids=(clue_constraint_id,),
                locale="en",
            ),
        ),
        givens=tuple(
            AssignmentAtom(variable_id=variable_id, value_id=value.value_id)
            for variable_id, value in zip(
                categories[-1].variable_ids,
                anchor_domain.values,
                strict=True,
            )
        ),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
        categories=categories,
        anchor_category_id=categories[-1].category_id,
    )


def test_specification_round_trip_preserves_canonical_identity() -> None:
    original = logic_grid_spec()
    restored = LogicGridSpec.model_validate_json(original.model_dump_json())
    assert restored == original
    assert canonical_sha256(restored) == canonical_sha256(original)


def test_family_and_schema_identity_are_fixed() -> None:
    payload = logic_grid_spec().model_dump()
    payload["identity"]["family_id"] = "another-family"
    with pytest.raises(ValidationError, match="family_id must be"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["identity"]["schema_version"] = "2.0.0"
    with pytest.raises(ValidationError, match="schema_version must be"):
        LogicGridSpec.model_validate(payload)


def test_categories_are_unique_equal_sized_and_cover_domains() -> None:
    payload = logic_grid_spec().model_dump()
    payload["categories"][1]["category_id"] = payload["categories"][0]["category_id"]
    with pytest.raises(ValidationError, match="category identifiers must be unique"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["domains"][1]["values"] = payload["domains"][1]["values"][:-1]
    with pytest.raises(ValidationError, match="same size"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["categories"][1]["domain_id"] = payload["categories"][0]["domain_id"]
    with pytest.raises(ValidationError, match="different domain"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["domains"][1]["values"][0]["value_id"] = payload["domains"][0]["values"][0]["value_id"]
    with pytest.raises(ValidationError, match="globally unique"):
        LogicGridSpec.model_validate(payload)


def test_category_variables_partition_items_and_use_the_anchor_domain() -> None:
    payload = logic_grid_spec().model_dump()
    payload["categories"][1]["variable_ids"] = (
        payload["categories"][0]["variable_ids"][0],
        *payload["categories"][1]["variable_ids"][1:],
    )
    with pytest.raises(ValidationError, match="variable references must be unique"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["variables"][0]["domain_id"] = payload["domains"][0]["domain_id"]
    with pytest.raises(ValidationError, match="over the anchor domain"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["variables"][0]["label"] = "Different label"
    with pytest.raises(ValidationError, match="align with domain values"):
        LogicGridSpec.model_validate(payload)


def test_each_category_has_one_exact_bijection_constraint() -> None:
    payload = logic_grid_spec().model_dump()
    payload["constraints"][1]["variable_ids"] = payload["constraints"][0]["variable_ids"]
    with pytest.raises(ValidationError, match="cover each category exactly once"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["constraints"][0]["source_clue_id"] = payload["clues"][0]["clue_id"]
    with pytest.raises(ValidationError, match="cover each category exactly once"):
        LogicGridSpec.model_validate(payload)


def test_anchor_assignments_are_complete_consistent_and_reference_closed() -> None:
    payload = logic_grid_spec().model_dump()
    payload["givens"] = payload["givens"][:-1]
    with pytest.raises(ValidationError, match="anchor category variables must be assigned"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["givens"] = (*payload["givens"], payload["givens"][0])
    with pytest.raises(ValidationError, match="duplicate atoms"):
        LogicGridSpec.model_validate(payload)

    original = logic_grid_spec()
    conflicting = original.model_copy(
        update={
            "givens": (
                *original.givens,
                ExclusionAtom(
                    variable_id=original.categories[-1].variable_ids[0],
                    value_id=original.domains[-1].values[0].value_id,
                ),
            )
        }
    )
    with pytest.raises(ValidationError, match="cannot also be excluded"):
        LogicGridSpec.model_validate(conflicting.model_dump())


def test_expression_references_and_family_catalogue_are_enforced() -> None:
    payload = logic_grid_spec().model_dump()
    payload["constraints"][-1]["expression"]["left"]["variable_id"] = (
        "deductra:variable:logic-grid:unknown"
    )
    with pytest.raises(ValidationError, match="unknown variable"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["constraints"][-1]["expression"] = Equal(
        left=Add(
            operands=(
                VariableReference(variable_id=payload["variables"][0]["variable_id"]),
                VariableReference(variable_id=payload["variables"][1]["variable_id"]),
            )
        ),
        right=VariableReference(variable_id=payload["variables"][2]["variable_id"]),
    ).model_dump()
    with pytest.raises(ValidationError, match="unsupported Logic Grid numeric expression"):
        LogicGridSpec.model_validate(payload)


def test_ordered_clues_require_an_ordered_anchor_category() -> None:
    payload = logic_grid_spec().model_dump()
    payload["constraints"][-1]["expression"] = LessThan(
        left=VariableReference(variable_id=payload["variables"][0]["variable_id"]),
        right=VariableReference(variable_id=payload["variables"][1]["variable_id"]),
    ).model_dump()
    assert LogicGridSpec.model_validate(payload)

    payload["domains"][-1]["ordered"] = False
    payload["domains"][-1]["values"] = tuple(
        {**value, "ordinal": None} for value in payload["domains"][-1]["values"]
    )
    with pytest.raises(ValidationError, match="ordered anchor category"):
        LogicGridSpec.model_validate(payload)


def test_anchor_order_and_numeric_metadata_are_complete() -> None:
    payload = logic_grid_spec().model_dump()
    payload["domains"][-1]["values"][1]["ordinal"] = 4
    with pytest.raises(ValidationError, match=r"ordinals 1\.\.n"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["domains"][-1]["values"][1]["numeric_value"] = None
    with pytest.raises(ValidationError, match="either complete or absent"):
        LogicGridSpec.model_validate(payload)


def test_numeric_difference_and_exclusive_alternative_clues_are_supported() -> None:
    payload = logic_grid_spec().model_dump()
    variable_ids = tuple(variable["variable_id"] for variable in payload["variables"])
    numeric_difference = Equal(
        left=Subtract(
            left=VariableReference(variable_id=variable_ids[0]),
            right=VariableReference(variable_id=variable_ids[1]),
        ),
        right=Constant(value=1),
    )
    payload["constraints"][-1]["expression"] = numeric_difference.model_dump()
    assert LogicGridSpec.model_validate(payload)

    exclusive_alternative = Xor(
        left=Equal(
            left=VariableReference(variable_id=variable_ids[0]),
            right=VariableReference(variable_id=variable_ids[3]),
        ),
        right=Equal(
            left=VariableReference(variable_id=variable_ids[0]),
            right=VariableReference(variable_id=variable_ids[4]),
        ),
    )
    payload["constraints"][-1]["expression"] = exclusive_alternative.model_dump()
    assert LogicGridSpec.model_validate(payload)


def test_clues_cover_constraints_and_preserve_primary_provenance() -> None:
    payload = logic_grid_spec().model_dump()
    payload["clues"][0]["constraint_ids"] = ()
    with pytest.raises(ValidationError, match="reference a constraint"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["constraints"][-1]["source_clue_id"] = "deductra:clue:logic-grid:unknown"
    with pytest.raises(ValidationError, match="provenance must match"):
        LogicGridSpec.model_validate(payload)

    payload = logic_grid_spec().model_dump()
    payload["constraints"][-1]["expression"] = Equal(
        left=Constant(value=1),
        right=Constant(value=1),
    ).model_dump()
    with pytest.raises(ValidationError, match="must reference an item variable"):
        LogicGridSpec.model_validate(payload)


def test_family_schema_has_a_stable_public_identity() -> None:
    schema = logic_grid_spec_json_schema()
    assert schema["$id"] == "urn:deductra:schema:logic-grid-spec:1"
    assert schema["title"] == "Deductra Logic Grid Specification v1"
    identity = schema["$defs"]["PuzzleIdentity"]["properties"]
    assert identity["family_id"]["const"] == FAMILY_ID
    assert identity["schema_version"]["const"] == SPEC_SCHEMA_VERSION


def test_checked_in_family_schema_is_current() -> None:
    schema_path = REPOSITORY_ROOT / "schemas" / "logic-grid-spec-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == rendered_logic_grid_spec_json_schema()
