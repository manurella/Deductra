"""Acceptance evidence for bounded Logic Grid structured import and export."""

from __future__ import annotations

from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from deductra.domain.serialization import canonical_json
from deductra.families.logic_grid import (
    MAX_STRUCTURED_COLLECTION_ITEMS,
    MAX_STRUCTURED_DEPTH,
    MAX_STRUCTURED_INPUT_BYTES,
    MAX_STRUCTURED_NODES,
    AssociationTemplate,
    BuilderItemRef,
    BuilderStatus,
    LogicGridBuilderCategory,
    LogicGridBuilderClue,
    LogicGridBuilderDraft,
    LogicGridBuilderItem,
    StructuredFormat,
    StructuredInputErrorCode,
    export_logic_grid_builder_json,
    export_logic_grid_builder_yaml,
    import_logic_grid_builder,
    logic_grid_structured_import_json_schema,
    rendered_logic_grid_structured_import_json_schema,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _ref(category: str, item: str) -> BuilderItemRef:
    return BuilderItemRef(category_key=category, item_key=item)


def _category(key: str, label: str, first: str, second: str) -> LogicGridBuilderCategory:
    return LogicGridBuilderCategory(
        category_key=key,
        label=label,
        items=(
            LogicGridBuilderItem(item_key="one", label=first),
            LogicGridBuilderItem(item_key="two", label=second),
        ),
    )


def _draft() -> LogicGridBuilderDraft:
    return LogicGridBuilderDraft(
        draft_id="evening-crossing",
        title="Evening Crossing",
        author="Example Author",
        created_at=datetime(2026, 7, 20, 14, 30, tzinfo=UTC),
        anchor_category_key="people",
        categories=(
            _category("people", "People", "Ana", "Bryn"),
            _category("boats", "Boats", "Élan", "Tern"),
            _category("drinks", "Drinks", "Tea", "Water"),
        ),
        clues=(
            LogicGridBuilderClue(
                clue_key="elan-ana",
                predicate=AssociationTemplate(
                    left=_ref("boats", "one"),
                    right=_ref("people", "one"),
                    relation="same",
                ),
            ),
            LogicGridBuilderClue(
                clue_key="tea-bryn",
                predicate=AssociationTemplate(
                    left=_ref("drinks", "one"),
                    right=_ref("people", "two"),
                    relation="same",
                ),
            ),
        ),
    )


def test_canonical_json_import_returns_the_normalized_builder_preview() -> None:
    draft = _draft()
    encoded = export_logic_grid_builder_json(draft)
    result = import_logic_grid_builder(encoded.encode("utf-8"), format=StructuredFormat.JSON)

    assert result.accepted
    assert result.errors == ()
    assert result.draft == draft
    assert result.assessment is not None
    assert result.assessment.status is BuilderStatus.UNPROVEN
    assert result.normalized_preview is not None
    assert result.normalized_preview.startswith("Evening Crossing\nStatus: unproven\n")
    assert encoded == export_logic_grid_builder_json(draft)
    assert encoded.endswith("\n")


def test_human_readable_yaml_is_deterministic_safe_and_round_trips() -> None:
    draft = _draft()
    encoded = export_logic_grid_builder_yaml(draft)
    result = import_logic_grid_builder(encoded, format="yaml")

    assert result.accepted
    assert result.draft == draft
    assert encoded == export_logic_grid_builder_yaml(draft)
    assert encoded.startswith("---\nschema_version: 1.0.0\n")
    assert "!!python" not in encoded
    assert "&id" not in encoded
    assert "*id" not in encoded


def test_json_and_yaml_imports_have_the_same_canonical_meaning() -> None:
    draft = _draft()
    json_result = import_logic_grid_builder(export_logic_grid_builder_json(draft), format="json")
    yaml_result = import_logic_grid_builder(export_logic_grid_builder_yaml(draft), format="yaml")

    assert json_result.draft is not None
    assert yaml_result.draft is not None
    assert canonical_json(json_result.draft) == canonical_json(yaml_result.draft)
    assert json_result.normalized_preview == yaml_result.normalized_preview


def test_exact_rational_values_round_trip_without_float_coercion() -> None:
    draft = _draft()
    anchor = draft.categories[0]
    categories = (
        anchor.model_copy(
            update={
                "items": (
                    anchor.items[0].model_copy(update={"numeric_value": Fraction(1, 3)}),
                    anchor.items[1].model_copy(update={"numeric_value": Fraction(2, 3)}),
                )
            }
        ),
        *draft.categories[1:],
    )
    rational_draft = draft.model_copy(update={"categories": categories})

    for format_, encoded in (
        ("json", export_logic_grid_builder_json(rational_draft)),
        ("yaml", export_logic_grid_builder_yaml(rational_draft)),
    ):
        result = import_logic_grid_builder(encoded, format=format_)
        assert result.accepted
        assert result.draft is not None
        assert result.draft == rational_draft
        assert result.draft.categories[0].items[0].numeric_value == Fraction(1, 3)


def test_verified_import_uses_the_existing_fail_closed_readiness_gate() -> None:
    result = import_logic_grid_builder(
        export_logic_grid_builder_json(_draft()),
        format="json",
        verify=True,
    )

    assert result.accepted
    assert result.assessment is not None
    assert result.assessment.status is BuilderStatus.VALID
    assert result.assessment.proof is not None
    assert result.assessment.proof.human_solvable
    assert result.assessment.proof.unique


def test_syntax_errors_report_format_location_and_correction() -> None:
    json_result = import_logic_grid_builder('{\n  "title":,\n}', format="json")
    yaml_result = import_logic_grid_builder("title: [broken\n", format="yaml")

    for result, format_ in (
        (json_result, StructuredFormat.JSON),
        (yaml_result, StructuredFormat.YAML),
    ):
        assert not result.accepted
        assert result.format is format_
        assert result.errors[0].code is StructuredInputErrorCode.SYNTAX_ERROR
        assert result.errors[0].line is not None
        assert result.errors[0].column is not None
        assert result.errors[0].correction


def test_model_errors_are_field_scoped_and_do_not_echo_input_values() -> None:
    payload = _draft().model_dump(mode="json")
    payload["categories"][1]["items"][0]["label"] = {"private": "do-not-echo"}
    result = import_logic_grid_builder(canonical_json(payload), format="json")

    assert not result.accepted
    error = next(item for item in result.errors if item.path == "categories[1].items[0].label")
    assert error.code is StructuredInputErrorCode.SCHEMA_ERROR
    assert error.expected
    assert error.received == "object (1 fields)"
    assert "do-not-echo" not in canonical_json(result)


def test_duplicate_keys_are_rejected_in_both_formats() -> None:
    json_result = import_logic_grid_builder('{"title":"One","title":"Two"}', format="json")
    yaml_result = import_logic_grid_builder("title: One\ntitle: Two\n", format="yaml")

    assert json_result.errors[0].code is StructuredInputErrorCode.DUPLICATE_KEY
    assert yaml_result.errors[0].code is StructuredInputErrorCode.DUPLICATE_KEY
    assert yaml_result.errors[0].line == 2
    assert yaml_result.errors[0].column == 1


def test_yaml_aliases_custom_tags_and_multiple_documents_are_rejected() -> None:
    cases = (
        ("title: &shared value\nauthor: *shared\n", StructuredInputErrorCode.UNSAFE_FEATURE),
        ("title: !!python/object/apply:builtins.str []\n", StructuredInputErrorCode.UNSAFE_FEATURE),
        ("<<: {title: One}\n", StructuredInputErrorCode.UNSAFE_FEATURE),
        ("title: One\n---\ntitle: Two\n", StructuredInputErrorCode.DOCUMENT_COUNT),
    )

    for source, expected in cases:
        result = import_logic_grid_builder(source, format="yaml")
        assert not result.accepted
        assert result.errors[0].code is expected


def test_format_encoding_size_and_root_failures_are_structured() -> None:
    cases = (
        import_logic_grid_builder("{}", format="toml"),
        import_logic_grid_builder(b"\xff", format="json"),
        import_logic_grid_builder("x" * (MAX_STRUCTURED_INPUT_BYTES + 1), format="json"),
        import_logic_grid_builder("[]", format="json"),
        import_logic_grid_builder(cast(Any, 42), format="json"),
    )
    assert tuple(result.errors[0].code for result in cases) == (
        StructuredInputErrorCode.UNSUPPORTED_FORMAT,
        StructuredInputErrorCode.INVALID_ENCODING,
        StructuredInputErrorCode.INPUT_TOO_LARGE,
        StructuredInputErrorCode.ROOT_TYPE,
        StructuredInputErrorCode.INVALID_SOURCE,
    )
    assert all(not result.accepted for result in cases)


def test_depth_and_collection_limits_apply_before_model_validation() -> None:
    nested = (
        '{"value":'
        + "[" * (MAX_STRUCTURED_DEPTH + 1)
        + "0"
        + "]" * (MAX_STRUCTURED_DEPTH + 1)
        + "}"
    )
    wide = canonical_json(
        {f"field-{index}": index for index in range(MAX_STRUCTURED_COLLECTION_ITEMS + 1)}
    )

    depth_result = import_logic_grid_builder(nested, format="json")
    collection_result = import_logic_grid_builder(wide, format="json")

    assert depth_result.errors[0].code is StructuredInputErrorCode.DEPTH_LIMIT
    assert collection_result.errors[0].code is StructuredInputErrorCode.COLLECTION_LIMIT


def test_total_node_limit_is_independent_of_per_collection_limit() -> None:
    wide_tree = {
        f"group-{group}": list(range(300)) for group in range((MAX_STRUCTURED_NODES // 300) + 2)
    }
    result = import_logic_grid_builder(canonical_json(wide_tree), format="json")

    assert not result.accepted
    assert result.errors[0].code is StructuredInputErrorCode.NODE_LIMIT


def test_nonfinite_and_non_json_yaml_values_fail_without_raw_exceptions() -> None:
    json_result = import_logic_grid_builder('{"revision": NaN}', format="json")
    yaml_result = import_logic_grid_builder("created_at: !!binary ZGF0YQ==\n", format="yaml")

    assert json_result.errors[0].code is StructuredInputErrorCode.SYNTAX_ERROR
    assert yaml_result.errors[0].code is StructuredInputErrorCode.UNSAFE_FEATURE


def test_empty_and_incomplete_documents_return_contract_results() -> None:
    empty = import_logic_grid_builder("", format="yaml")
    incomplete = import_logic_grid_builder(
        '{"draft_id":"new-draft","created_at":"2026-07-20T00:00:00Z"}',
        format="json",
    )

    assert empty.errors[0].code is StructuredInputErrorCode.ROOT_TYPE
    assert incomplete.accepted
    assert incomplete.assessment is not None
    assert incomplete.assessment.status is BuilderStatus.INCOMPLETE
    assert incomplete.normalized_preview is not None


def test_structured_import_result_schema_is_stable_and_checked_in() -> None:
    schema = logic_grid_structured_import_json_schema()
    schema_path = REPOSITORY_ROOT / "schemas" / "logic-grid-structured-import-v1.schema.json"

    assert schema["$id"] == "urn:deductra:schema:logic-grid-structured-import:1"
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert schema_path.read_text(encoding="utf-8") == (
        rendered_logic_grid_structured_import_json_schema()
    )
