"""Acceptance evidence for the Logic Grid guided-builder boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from deductra.domain.constraints import ArithmeticConstraint
from deductra.domain.expressions import (
    And,
    Cardinality,
    Equal,
    Equivalent,
    Implies,
    LessThan,
    Not,
    Or,
    Xor,
)
from deductra.families.logic_grid import (
    MAX_BUILDER_CATEGORIES,
    MAX_BUILDER_CLUES,
    MAX_BUILDER_PREDICATE_DEPTH,
    AllTemplate,
    AnyTemplate,
    AssociationTemplate,
    BuilderItemRef,
    BuilderMessageLevel,
    BuilderStage,
    BuilderStatus,
    CardinalityTemplate,
    ConditionalTemplate,
    EquivalentTemplate,
    ExclusiveTemplate,
    LogicGridBuilderCategory,
    LogicGridBuilderClue,
    LogicGridBuilderDraft,
    LogicGridBuilderItem,
    NegationTemplate,
    NumericDifferenceTemplate,
    OrderingTemplate,
    assess_logic_grid_builder,
    check_logic_grid_solution,
    logic_grid_builder_json_schema,
    rendered_logic_grid_builder_json_schema,
    rendered_logic_grid_builder_preview,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_CREATED_AT = datetime(2026, 7, 19, tzinfo=UTC)


def _ref(category: str, item: str) -> BuilderItemRef:
    return BuilderItemRef(category_key=category, item_key=item)


def _category(
    key: str,
    label: str,
    items: tuple[tuple[str, str], ...],
    *,
    numeric: tuple[int, ...] | None = None,
) -> LogicGridBuilderCategory:
    return LogicGridBuilderCategory(
        category_key=key,
        label=label,
        items=tuple(
            LogicGridBuilderItem(
                item_key=item_key,
                label=item_label,
                numeric_value=numeric[index] if numeric is not None else None,
            )
            for index, (item_key, item_label) in enumerate(items)
        ),
    )


def _match(key: str, left: tuple[str, str], right: tuple[str, str]) -> LogicGridBuilderClue:
    return LogicGridBuilderClue(
        clue_key=key,
        predicate=AssociationTemplate(
            left=_ref(*left),
            right=_ref(*right),
            relation="same",
        ),
    )


def complete_draft() -> LogicGridBuilderDraft:
    """Return a small user draft that is uniquely human-solvable."""
    return LogicGridBuilderDraft(
        draft_id="harbor-workshop",
        title="Harbor Workshop",
        author="Example Author",
        created_at=_CREATED_AT,
        anchor_category_key="visitors",
        categories=(
            _category(
                "visitors",
                "Visitors",
                (("ari", "Ari"), ("bela", "Bela"), ("cora", "Cora")),
                numeric=(10, 20, 30),
            ),
            _category(
                "boats",
                "Boats",
                (("kestrel", "Kestrel"), ("lumen", "Lumen"), ("tern", "Tern")),
            ),
            _category(
                "drinks",
                "Drinks",
                (("cocoa", "Cocoa"), ("tea", "Mint Tea"), ("cider", "Cider")),
            ),
        ),
        clues=(
            _match("kestrel-bela", ("boats", "kestrel"), ("visitors", "bela")),
            _match("lumen-cora", ("boats", "lumen"), ("visitors", "cora")),
            _match("cocoa-cora", ("drinks", "cocoa"), ("visitors", "cora")),
            _match("tea-ari", ("drinks", "tea"), ("visitors", "ari")),
        ),
    )


def test_complete_draft_compiles_to_a_deterministic_normalized_preview() -> None:
    draft = complete_draft()
    first = assess_logic_grid_builder(draft)
    second = assess_logic_grid_builder(draft)

    assert first == second
    assert first.status is BuilderStatus.UNPROVEN
    assert first.stage is BuilderStage.PREVIEW
    assert first.puzzle is not None
    assert first.preview is not None
    assert first.preview.dimensions == "3x3"
    assert first.preview.anchor_category == "Visitors"
    assert first.preview.category_table[1] == ("Boats", ("Kestrel", "Lumen", "Tern"))
    assert first.preview.clue_texts[0] == "Kestrel is associated with Bela."
    assert first.preview.puzzle_spec_hash == (
        "10a3fa259a54998c11e30d5c6adf35d4e3d77986a26fa5ef31012e0059eb8d10"
    )
    assert first.draft_hash == ("c6529a32faa1ac0ff0f89b7590acee21caa58134336a817f2f0dca9e79d0d506")
    assert first.puzzle.identity.source_kind == "user"
    assert first.puzzle.identity.metadata["builder_schema_version"] == "1.0.0"
    assert first.puzzle.identity.puzzle_id.endswith(":harbor-workshop")
    assert first.messages[-1].level is BuilderMessageLevel.UNPROVEN


def test_verified_assessment_proves_human_solvability_and_uniqueness() -> None:
    assessment = assess_logic_grid_builder(complete_draft(), verify=True)

    assert assessment.status is BuilderStatus.VALID
    assert assessment.stage is BuilderStage.READY
    assert assessment.puzzle is not None
    assert assessment.proof is not None
    assert assessment.proof.human_solvable
    assert assessment.proof.unique
    assert assessment.proof.verified_steps > 0
    assert len(assessment.proof.certificate_ids) == assessment.proof.verified_steps * 2
    assert check_logic_grid_solution(
        assessment.puzzle,
        assessment.proof.solution,
    ).accepted


def test_incomplete_draft_reports_what_where_why_and_correction() -> None:
    draft = LogicGridBuilderDraft(
        draft_id="new-puzzle",
        created_at=_CREATED_AT,
    )
    assessment = assess_logic_grid_builder(draft)

    assert assessment.status is BuilderStatus.INCOMPLETE
    assert assessment.stage is BuilderStage.PROFILE
    assert assessment.puzzle is None
    assert {message.path for message in assessment.messages} >= {
        "title",
        "categories",
        "anchor_category_key",
        "clues",
    }
    assert all(
        message.problem and message.reason and message.correction for message in assessment.messages
    )
    rendered = rendered_logic_grid_builder_preview(assessment)
    assert "[incomplete] title:" in rendered
    assert "Enter a plain-text title." in rendered


def test_semantic_errors_are_field_scoped_and_do_not_compile() -> None:
    draft = complete_draft().model_copy(
        update={
            "categories": (
                *complete_draft().categories[:-1],
                _category(
                    "drinks",
                    "Drinks",
                    (("cocoa", "Cocoa"), ("tea", "Mint Tea")),
                ),
            ),
            "clues": (
                LogicGridBuilderClue(
                    clue_key="unknown-reference",
                    predicate=AssociationTemplate(
                        left=_ref("boats", "missing"),
                        right=_ref("visitors", "ari"),
                        relation="same",
                    ),
                ),
            ),
        }
    )
    assessment = assess_logic_grid_builder(draft)

    assert assessment.status is BuilderStatus.INVALID
    assert assessment.puzzle is None
    assert any(
        message.path == "categories[2].items" and "differs" in message.problem
        for message in assessment.messages
    )
    assert any(
        message.path == "clues[0].predicate" and "Unknown item" in message.problem
        for message in assessment.messages
    )


def test_numeric_templates_require_complete_anchor_values() -> None:
    draft = complete_draft()
    categories = (
        draft.categories[0].model_copy(
            update={
                "items": (
                    *draft.categories[0].items[:-1],
                    draft.categories[0].items[-1].model_copy(update={"numeric_value": None}),
                )
            }
        ),
        *draft.categories[1:],
    )
    numeric = LogicGridBuilderClue(
        clue_key="numeric-gap",
        predicate=NumericDifferenceTemplate(
            greater=_ref("boats", "lumen"),
            lesser=_ref("drinks", "tea"),
            difference=10,
        ),
    )
    assessment = assess_logic_grid_builder(
        draft.model_copy(update={"categories": categories, "clues": (*draft.clues, numeric)})
    )

    assert assessment.status is BuilderStatus.INVALID
    assert any("numeric values are incomplete" in item.problem for item in assessment.messages)
    assert any("numeric-difference clue" in item.problem for item in assessment.messages)


def test_full_guided_template_catalogue_compiles_to_normalized_expressions() -> None:
    draft = complete_draft()
    a = AssociationTemplate(
        left=_ref("boats", "kestrel"),
        right=_ref("visitors", "bela"),
        relation="same",
    )
    b = AssociationTemplate(
        left=_ref("drinks", "cocoa"),
        right=_ref("visitors", "cora"),
        relation="different",
    )
    templates = (
        AllTemplate(operands=(a, b)),
        AnyTemplate(operands=(a, b)),
        NegationTemplate(operand=a),
        ExclusiveTemplate(left=a, right=b),
        ConditionalTemplate(premise=a, conclusion=b),
        EquivalentTemplate(left=a, right=b),
        CardinalityTemplate(operands=(a, b), minimum=1, maximum=1),
        OrderingTemplate(
            earlier=_ref("boats", "kestrel"),
            later=_ref("drinks", "cocoa"),
        ),
        NumericDifferenceTemplate(
            greater=_ref("boats", "lumen"),
            lesser=_ref("drinks", "tea"),
            difference=10,
        ),
    )
    clues = tuple(
        LogicGridBuilderClue(clue_key=f"catalogue-{index}", predicate=template)
        for index, template in enumerate(templates, start=1)
    )
    assessment = assess_logic_grid_builder(draft.model_copy(update={"clues": clues}))

    assert assessment.status is BuilderStatus.UNPROVEN
    assert assessment.puzzle is not None
    expressions = tuple(
        constraint.expression
        for constraint in assessment.puzzle.constraints
        if isinstance(constraint, ArithmeticConstraint)
    )
    assert tuple(type(item) for item in expressions) == (
        And,
        Or,
        Not,
        Xor,
        Implies,
        Equivalent,
        Cardinality,
        LessThan,
        Equal,
    )
    assert assessment.preview is not None
    assert all(text.endswith(".") for text in assessment.preview.clue_texts)


def test_duplicate_formal_clues_are_visible_warnings() -> None:
    draft = complete_draft()
    duplicate = draft.clues[0].model_copy(update={"clue_key": "duplicate-match"})
    assessment = assess_logic_grid_builder(
        draft.model_copy(update={"clues": (*draft.clues, duplicate)}),
        verify=True,
    )

    assert assessment.status is BuilderStatus.WARNING
    assert assessment.stage is BuilderStage.READY
    assert assessment.proof is not None
    assert any(message.level is BuilderMessageLevel.WARNING for message in assessment.messages)


def test_underconstrained_draft_remains_unproven_without_hidden_search() -> None:
    draft = complete_draft().model_copy(update={"clues": complete_draft().clues[:2]})
    assessment = assess_logic_grid_builder(draft, verify=True)

    assert assessment.status is BuilderStatus.UNPROVEN
    assert assessment.stage is BuilderStage.PROOF
    assert assessment.puzzle is not None
    assert assessment.proof is None
    assert any(
        "human reasoning ended" in message.problem.lower() for message in assessment.messages
    )


def test_preview_is_plain_deterministic_and_contains_formal_fingerprint() -> None:
    assessment = assess_logic_grid_builder(complete_draft())
    rendered = rendered_logic_grid_builder_preview(assessment)

    assert rendered == rendered_logic_grid_builder_preview(assessment)
    assert rendered.startswith("Harbor Workshop\nStatus: unproven\n")
    assert "Categories:\n- Visitors: Ari, Bela, Cora" in rendered
    assert "Formal model: 9 variables, 7 constraints" in rendered
    assert assessment.preview is not None
    assert rendered.endswith(
        "Run the verified proof check before saving or playing this revision.\n"
    )


def test_builder_schema_has_stable_identity_and_checked_in_projection() -> None:
    schema = logic_grid_builder_json_schema()
    assert schema["$id"] == "urn:deductra:schema:logic-grid-builder-draft:1"
    assert schema["title"] == "Deductra Logic Grid Builder Draft v1"
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    schema_path = REPOSITORY_ROOT / "schemas" / "logic-grid-builder-draft-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == rendered_logic_grid_builder_json_schema()


def test_guided_resource_and_text_bounds_fail_closed_with_actions() -> None:
    draft = complete_draft()
    extra_categories = tuple(
        _category(
            f"extra-{index}",
            f"Extra {index}",
            (("one", "One"), ("two", "Two"), ("three", "Three")),
        )
        for index in range(1, MAX_BUILDER_CATEGORIES - len(draft.categories) + 2)
    )
    predicate = draft.clues[0].predicate
    for _ in range(MAX_BUILDER_PREDICATE_DEPTH):
        predicate = NegationTemplate(operand=predicate)
    clues = tuple(
        LogicGridBuilderClue(clue_key=f"bounded-{index}", predicate=predicate)
        for index in range(1, MAX_BUILDER_CLUES + 2)
    )
    assessment = assess_logic_grid_builder(
        draft.model_copy(
            update={
                "title": "Unsafe\nTitle",
                "categories": (*draft.categories, *extra_categories),
                "clues": clues,
            }
        )
    )

    assert assessment.status is BuilderStatus.INVALID
    assert assessment.puzzle is None
    assert {message.path for message in assessment.messages} >= {
        "title",
        "categories",
        "clues",
        "clues[0].predicate",
    }
    assert all(message.correction for message in assessment.messages)


def test_same_category_association_is_rejected_as_misleading() -> None:
    draft = complete_draft().model_copy(
        update={
            "clues": (
                LogicGridBuilderClue(
                    clue_key="same-table",
                    predicate=AssociationTemplate(
                        left=_ref("boats", "kestrel"),
                        right=_ref("boats", "lumen"),
                        relation="different",
                    ),
                ),
            )
        }
    )
    assessment = assess_logic_grid_builder(draft)

    assert assessment.status is BuilderStatus.INVALID
    assert any("same category" in message.problem.lower() for message in assessment.messages)
