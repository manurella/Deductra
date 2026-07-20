"""Guided, immutable authoring boundary for Logic Grid puzzles."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from deductra.domain.atoms import AssignmentAtom
from deductra.domain.base import DomainModel
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    And,
    BooleanExpression,
    Cardinality,
    Constant,
    Equal,
    Equivalent,
    Implies,
    LessThan,
    Not,
    NotEqual,
    Or,
    Subtract,
    VariableReference,
    Xor,
)
from deductra.domain.puzzle import (
    Clue,
    DisplaySpec,
    ProvenanceBundle,
    ProvenanceReference,
    PuzzleIdentity,
)
from deductra.domain.serialization import canonical_sha256
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_grid.checker import check_logic_grid_solution
from deductra.families.logic_grid.solver import logic_grid_rules
from deductra.families.logic_grid.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridCategory,
    LogicGridSpec,
)
from deductra.reasoning import (
    GENESIS_EVENT_HASH,
    HumanReasoningEngine,
    HumanSolveContext,
    HumanSolveStatus,
    ProducerRef,
    create_initial_state,
    reduce_state,
)
from deductra.verification import (
    CpSatProofBackend,
    CrossVerificationCoordinator,
    VerifiedRuleAuthority,
    Z3ProofBackend,
)

BUILDER_SCHEMA_VERSION = "1.0.0"
MAX_BUILDER_CATEGORIES = 8
MAX_BUILDER_ITEMS_PER_CATEGORY = 8
MAX_BUILDER_CLUES = 128
MAX_BUILDER_PREDICATE_DEPTH = 16

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_MAX_LABEL_LENGTH = 120
_MAX_CLUE_TEXT_LENGTH = 1_000


class BuilderStatus(StrEnum):
    """Stable aggregate status for a guided draft assessment."""

    VALID = "valid"
    WARNING = "warning"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    UNPROVEN = "unproven"


class BuilderStage(StrEnum):
    """Progressive authoring stage reached by one immutable draft."""

    PROFILE = "profile"
    CATEGORIES = "categories"
    CLUES = "clues"
    PREVIEW = "preview"
    PROOF = "proof"
    READY = "ready"


class BuilderMessageLevel(StrEnum):
    """Severity of one actionable validation message."""

    WARNING = "warning"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    UNPROVEN = "unproven"


class BuilderItemRef(DomainModel):
    """User-facing reference to one item in a named category."""

    category_key: str
    item_key: str


class AssociationTemplate(DomainModel):
    """Same-row or different-row association template."""

    kind: Literal["association"] = "association"
    left: BuilderItemRef
    right: BuilderItemRef
    relation: Literal["same", "different"]


class OrderingTemplate(DomainModel):
    """Strict before relationship over ordered anchor rows."""

    kind: Literal["ordering"] = "ordering"
    earlier: BuilderItemRef
    later: BuilderItemRef


class NumericDifferenceTemplate(DomainModel):
    """Exact positive difference over declared anchor numeric values."""

    kind: Literal["numeric_difference"] = "numeric_difference"
    greater: BuilderItemRef
    lesser: BuilderItemRef
    difference: int | Fraction

    @model_validator(mode="after")
    def require_positive_difference(self) -> Self:
        if isinstance(self.difference, bool) or self.difference <= 0:
            raise ValueError("numeric difference must be a positive exact value")
        return self


class AllTemplate(DomainModel):
    """Conjunction of two or more guided predicates."""

    kind: Literal["all"] = "all"
    operands: tuple[BuilderPredicate, ...]

    @model_validator(mode="after")
    def require_operands(self) -> Self:
        if len(self.operands) < 2:
            raise ValueError("all template requires at least two operands")
        return self


class AnyTemplate(DomainModel):
    """Inclusive alternative over two or more guided predicates."""

    kind: Literal["any"] = "any"
    operands: tuple[BuilderPredicate, ...]

    @model_validator(mode="after")
    def require_operands(self) -> Self:
        if len(self.operands) < 2:
            raise ValueError("any template requires at least two operands")
        return self


class NegationTemplate(DomainModel):
    """Logical negation of one guided predicate."""

    kind: Literal["not"] = "not"
    operand: BuilderPredicate


class ExclusiveTemplate(DomainModel):
    """Exclusive alternative between two guided predicates."""

    kind: Literal["exclusive"] = "exclusive"
    left: BuilderPredicate
    right: BuilderPredicate


class ConditionalTemplate(DomainModel):
    """Implication between two guided predicates."""

    kind: Literal["conditional"] = "conditional"
    premise: BuilderPredicate
    conclusion: BuilderPredicate


class EquivalentTemplate(DomainModel):
    """Logical equivalence between two guided predicates."""

    kind: Literal["equivalent"] = "equivalent"
    left: BuilderPredicate
    right: BuilderPredicate


class CardinalityTemplate(DomainModel):
    """Bounded number of true guided predicates."""

    kind: Literal["cardinality"] = "cardinality"
    operands: tuple[BuilderPredicate, ...]
    minimum: int
    maximum: int

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if not self.operands:
            raise ValueError("cardinality template requires at least one operand")
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("cardinality bounds must satisfy 0 <= minimum <= maximum")
        if self.maximum > len(self.operands):
            raise ValueError("cardinality maximum cannot exceed the operand count")
        return self


BuilderPredicate = Annotated[
    AssociationTemplate
    | OrderingTemplate
    | NumericDifferenceTemplate
    | AllTemplate
    | AnyTemplate
    | NegationTemplate
    | ExclusiveTemplate
    | ConditionalTemplate
    | EquivalentTemplate
    | CardinalityTemplate,
    Field(discriminator="kind"),
]


class LogicGridBuilderItem(DomainModel):
    """One item entered in a guided category table."""

    item_key: str
    label: str
    numeric_value: int | Fraction | None = None


class LogicGridBuilderCategory(DomainModel):
    """One category table entered through the guided builder."""

    category_key: str
    label: str
    items: tuple[LogicGridBuilderItem, ...] = ()


class LogicGridBuilderClue(DomainModel):
    """One guided clue and its optional author-supplied presentation text."""

    clue_key: str
    predicate: BuilderPredicate
    text: str | None = None


class LogicGridBuilderDraft(DomainModel):
    """Incomplete-safe, immutable input model for one authoring revision."""

    schema_version: str = BUILDER_SCHEMA_VERSION
    draft_id: str
    revision: int = 1
    title: str = ""
    author: str | None = None
    locale: str = "en"
    created_at: datetime
    anchor_category_key: str = ""
    categories: tuple[LogicGridBuilderCategory, ...] = ()
    clues: tuple[LogicGridBuilderClue, ...] = ()

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        if self.schema_version != BUILDER_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {BUILDER_SCHEMA_VERSION!r}")
        if self.revision < 1:
            raise ValueError("revision must be positive")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone offset")
        return self


class BuilderValidationMessage(DomainModel):
    """Actionable validation feedback suitable for any presentation adapter."""

    level: BuilderMessageLevel
    path: str
    problem: str
    reason: str
    correction: str


class LogicGridBuilderPreview(DomainModel):
    """Normalized category, clue, grid, and formal-model preview."""

    title: str
    dimensions: str
    anchor_category: str
    category_table: tuple[tuple[str, tuple[str, ...]], ...]
    association_grid: tuple[tuple[str, tuple[str, ...]], ...]
    clue_texts: tuple[str, ...]
    variable_count: int
    constraint_count: int
    puzzle_spec_hash: str


class LogicGridBuilderProof(DomainModel):
    """Evidence that verified human reasoning reached one unique solution."""

    human_solvable: bool
    unique: bool
    trace_hash: str
    final_state_hash: str
    verified_steps: int
    certificate_ids: tuple[str, ...]
    solution: tuple[AssignmentAtom, ...]


class LogicGridBuilderAssessment(DomainModel):
    """Complete staged result returned instead of UI-facing exceptions."""

    draft_hash: str
    status: BuilderStatus
    stage: BuilderStage
    messages: tuple[BuilderValidationMessage, ...] = ()
    preview: LogicGridBuilderPreview | None = None
    puzzle: LogicGridSpec | None = None
    proof: LogicGridBuilderProof | None = None


for model in (
    AllTemplate,
    AnyTemplate,
    NegationTemplate,
    ExclusiveTemplate,
    ConditionalTemplate,
    EquivalentTemplate,
    CardinalityTemplate,
    LogicGridBuilderClue,
):
    model.model_rebuild()


def _message(
    level: BuilderMessageLevel,
    path: str,
    problem: str,
    reason: str,
    correction: str,
) -> BuilderValidationMessage:
    return BuilderValidationMessage(
        level=level,
        path=path,
        problem=problem,
        reason=reason,
        correction=correction,
    )


def _invalid_text(value: str, maximum: int) -> str | None:
    if not value.strip():
        return "must not be blank"
    if len(value) > maximum:
        return f"must contain at most {maximum} characters"
    if any(unicodedata.category(character).startswith("C") for character in value):
        return "must not contain control or formatting characters"
    return None


def _predicate_children(predicate: BuilderPredicate) -> tuple[BuilderPredicate, ...]:
    if isinstance(predicate, (AllTemplate, AnyTemplate, CardinalityTemplate)):
        return predicate.operands
    if isinstance(predicate, NegationTemplate):
        return (predicate.operand,)
    if isinstance(predicate, (ExclusiveTemplate, EquivalentTemplate)):
        return predicate.left, predicate.right
    if isinstance(predicate, ConditionalTemplate):
        return predicate.premise, predicate.conclusion
    return ()


def _predicate_refs(predicate: BuilderPredicate) -> tuple[BuilderItemRef, ...]:
    if isinstance(predicate, AssociationTemplate):
        return predicate.left, predicate.right
    if isinstance(predicate, OrderingTemplate):
        return predicate.earlier, predicate.later
    if isinstance(predicate, NumericDifferenceTemplate):
        return predicate.greater, predicate.lesser
    return tuple(ref for child in _predicate_children(predicate) for ref in _predicate_refs(child))


def _predicate_depth(predicate: BuilderPredicate) -> int:
    children = _predicate_children(predicate)
    return 1 if not children else 1 + max(_predicate_depth(child) for child in children)


def _validate_draft(draft: LogicGridBuilderDraft) -> tuple[BuilderValidationMessage, ...]:
    messages: list[BuilderValidationMessage] = []
    if not _KEY_PATTERN.fullmatch(draft.draft_id):
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "draft_id",
                "Draft identifier is not a safe key.",
                "Stable identifiers use lowercase letters, digits, and internal hyphens.",
                "Start with a lowercase letter and use at most 64 key characters.",
            )
        )
    title_error = _invalid_text(draft.title, _MAX_LABEL_LENGTH)
    if title_error:
        messages.append(
            _message(
                BuilderMessageLevel.INCOMPLETE
                if not draft.title.strip()
                else BuilderMessageLevel.INVALID,
                "title",
                f"Puzzle title {title_error}.",
                "A concise title identifies the immutable puzzle revision.",
                "Enter a plain-text title.",
            )
        )
    if draft.author is not None:
        author_error = _invalid_text(draft.author, _MAX_LABEL_LENGTH)
        if author_error:
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    "author",
                    f"Author name {author_error}.",
                    "Authorship is retained in public puzzle provenance.",
                    "Use a non-empty plain-text author name or omit it.",
                )
            )
    if not draft.locale.strip() or len(draft.locale) > 35:
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "locale",
                "Locale is empty or too long.",
                "Clue presentation requires one bounded locale identifier.",
                "Use a locale such as 'en' or 'en-GB'.",
            )
        )
    if len(draft.categories) < 3:
        messages.append(
            _message(
                BuilderMessageLevel.INCOMPLETE,
                "categories",
                "At least three categories are required.",
                "Logic Grid puzzles associate equal-sized category tables.",
                "Add categories until at least three are present.",
            )
        )
    if len(draft.categories) > MAX_BUILDER_CATEGORIES:
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "categories",
                "The guided category limit is exceeded.",
                "Bounded authoring prevents accidental resource exhaustion.",
                f"Use at most {MAX_BUILDER_CATEGORIES} categories.",
            )
        )

    category_keys = tuple(category.category_key for category in draft.categories)
    category_labels = tuple(category.label.strip() for category in draft.categories)
    if len(category_keys) != len(set(category_keys)):
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "categories",
                "Category keys must be unique.",
                "Item references use category keys as stable coordinates.",
                "Rename each repeated category key.",
            )
        )
    if len(category_labels) != len(set(category_labels)):
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "categories",
                "Category labels must be unique.",
                "Distinct visible headings prevent ambiguous clues.",
                "Give every category a different label.",
            )
        )

    item_lookup: dict[tuple[str, str], LogicGridBuilderItem] = {}
    expected_size = len(draft.categories[0].items) if draft.categories else 0
    for category_index, category in enumerate(draft.categories):
        path = f"categories[{category_index}]"
        if not _KEY_PATTERN.fullmatch(category.category_key):
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.category_key",
                    "Category key is not valid.",
                    "Stable keys are used to derive canonical identifiers.",
                    "Use lowercase letters, digits, and internal hyphens.",
                )
            )
        label_error = _invalid_text(category.label, _MAX_LABEL_LENGTH)
        if label_error:
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.label",
                    f"Category label {label_error}.",
                    "Every table requires a readable heading.",
                    "Enter a unique plain-text category label.",
                )
            )
        if len(category.items) < 2:
            messages.append(
                _message(
                    BuilderMessageLevel.INCOMPLETE,
                    f"{path}.items",
                    "At least two items are required.",
                    "A category cannot form a permutation with fewer than two items.",
                    "Add items to this category.",
                )
            )
        if len(category.items) > MAX_BUILDER_ITEMS_PER_CATEGORY:
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.items",
                    "The guided item limit is exceeded.",
                    "Bounded category size protects interactive validation.",
                    f"Use at most {MAX_BUILDER_ITEMS_PER_CATEGORY} items.",
                )
            )
        if expected_size >= 2 and len(category.items) != expected_size:
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.items",
                    "Category size differs from the other category tables.",
                    "Logic Grid categories must form equal-sized bijections.",
                    f"Use exactly {expected_size} items in every category.",
                )
            )
        item_keys = tuple(item.item_key for item in category.items)
        item_labels = tuple(item.label.strip() for item in category.items)
        if len(item_keys) != len(set(item_keys)):
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.items",
                    "Item keys must be unique within a category.",
                    "Guided clues address items through their keys.",
                    "Rename each repeated item key.",
                )
            )
        if len(item_labels) != len(set(item_labels)):
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.items",
                    "Item labels must be unique within a category.",
                    "Repeated visible labels make clue text ambiguous.",
                    "Give every item in this category a different label.",
                )
            )
        for item_index, item in enumerate(category.items):
            item_path = f"{path}.items[{item_index}]"
            if not _KEY_PATTERN.fullmatch(item.item_key):
                messages.append(
                    _message(
                        BuilderMessageLevel.INVALID,
                        f"{item_path}.item_key",
                        "Item key is not valid.",
                        "Stable keys are used to derive canonical identifiers.",
                        "Use lowercase letters, digits, and internal hyphens.",
                    )
                )
            label_error = _invalid_text(item.label, _MAX_LABEL_LENGTH)
            if label_error:
                messages.append(
                    _message(
                        BuilderMessageLevel.INVALID,
                        f"{item_path}.label",
                        f"Item label {label_error}.",
                        "Each grid item needs a readable visible label.",
                        "Enter a unique plain-text item label.",
                    )
                )
            item_lookup[(category.category_key, item.item_key)] = item

    if not draft.anchor_category_key:
        messages.append(
            _message(
                BuilderMessageLevel.INCOMPLETE,
                "anchor_category_key",
                "An anchor category has not been selected.",
                "The anchor defines canonical row identity and order.",
                "Choose one declared category as the anchor.",
            )
        )
    elif draft.anchor_category_key not in set(category_keys):
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "anchor_category_key",
                "The selected anchor category does not exist.",
                "Canonical rows must come from a declared category.",
                "Select one of the current category keys.",
            )
        )

    anchor = next(
        (
            category
            for category in draft.categories
            if category.category_key == draft.anchor_category_key
        ),
        None,
    )
    if anchor is not None:
        numeric_values = tuple(item.numeric_value for item in anchor.items)
        if any(value is not None for value in numeric_values):
            if any(value is None for value in numeric_values):
                messages.append(
                    _message(
                        BuilderMessageLevel.INVALID,
                        "categories.anchor.items",
                        "Anchor numeric values are incomplete.",
                        "Numeric clue templates require a value for every anchor row.",
                        "Enter all numeric values or remove all of them.",
                    )
                )
            elif len(numeric_values) != len(set(numeric_values)):
                messages.append(
                    _message(
                        BuilderMessageLevel.INVALID,
                        "categories.anchor.items",
                        "Anchor numeric values must be unique.",
                        "Each canonical row needs one unambiguous numeric meaning.",
                        "Use a different exact value for each anchor item.",
                    )
                )
    for category in draft.categories:
        if category.category_key != draft.anchor_category_key and any(
            item.numeric_value is not None for item in category.items
        ):
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"categories.{category.category_key}.items",
                    "Numeric values are set outside the anchor category.",
                    "Logic Grid numeric semantics belong to canonical anchor rows.",
                    "Move numeric values to the anchor category or remove them.",
                )
            )

    if not draft.clues:
        messages.append(
            _message(
                BuilderMessageLevel.INCOMPLETE,
                "clues",
                "At least one clue is required.",
                "A puzzle without clues cannot establish its intended associations.",
                "Add a guided clue template.",
            )
        )
    if len(draft.clues) > MAX_BUILDER_CLUES:
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "clues",
                "The guided clue limit is exceeded.",
                "Bounded clue count protects validation and preview responsiveness.",
                f"Use at most {MAX_BUILDER_CLUES} clues.",
            )
        )
    clue_keys = tuple(clue.clue_key for clue in draft.clues)
    if len(clue_keys) != len(set(clue_keys)):
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "clues",
                "Clue keys must be unique.",
                "Constraint provenance uses each clue key exactly once.",
                "Rename each repeated clue key.",
            )
        )
    predicate_hashes: set[str] = set()
    has_numeric_template = False
    for clue_index, clue in enumerate(draft.clues):
        path = f"clues[{clue_index}]"
        if not _KEY_PATTERN.fullmatch(clue.clue_key):
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.clue_key",
                    "Clue key is not valid.",
                    "Stable keys bind presentation clues to formal constraints.",
                    "Use lowercase letters, digits, and internal hyphens.",
                )
            )
        if clue.text is not None:
            text_error = _invalid_text(clue.text, _MAX_CLUE_TEXT_LENGTH)
            if text_error:
                messages.append(
                    _message(
                        BuilderMessageLevel.INVALID,
                        f"{path}.text",
                        f"Clue text {text_error}.",
                        "Presentation text must be safe and readable.",
                        "Use bounded plain text or omit it for generated wording.",
                    )
                )
        if _predicate_depth(clue.predicate) > MAX_BUILDER_PREDICATE_DEPTH:
            messages.append(
                _message(
                    BuilderMessageLevel.INVALID,
                    f"{path}.predicate",
                    "The clue expression is nested too deeply.",
                    "A depth bound protects interactive validation from abusive input.",
                    f"Use at most {MAX_BUILDER_PREDICATE_DEPTH} nested template levels.",
                )
            )
        for ref in _predicate_refs(clue.predicate):
            if (ref.category_key, ref.item_key) not in item_lookup:
                messages.append(
                    _message(
                        BuilderMessageLevel.INVALID,
                        f"{path}.predicate",
                        f"Unknown item reference '{ref.category_key}.{ref.item_key}'.",
                        "Every clue reference must resolve to the current category tables.",
                        "Choose an existing category and item key.",
                    )
                )
        stack = [clue.predicate]
        while stack:
            predicate = stack.pop()
            stack.extend(_predicate_children(predicate))
            if isinstance(predicate, NumericDifferenceTemplate):
                has_numeric_template = True
            if isinstance(predicate, AssociationTemplate):
                if predicate.left == predicate.right:
                    messages.append(
                        _message(
                            BuilderMessageLevel.INVALID,
                            f"{path}.predicate",
                            "An association compares an item with itself.",
                            "Self-comparisons are tautological or contradictory, not useful clues.",
                            "Select two different items.",
                        )
                    )
                elif predicate.left.category_key == predicate.right.category_key:
                    messages.append(
                        _message(
                            BuilderMessageLevel.INVALID,
                            f"{path}.predicate",
                            "A direct association compares items in the same category.",
                            "Category bijection already separates distinct items in one table.",
                            "Associate items from different categories.",
                        )
                    )
        predicate_hash = canonical_sha256(clue.predicate)
        if predicate_hash in predicate_hashes:
            messages.append(
                _message(
                    BuilderMessageLevel.WARNING,
                    f"{path}.predicate",
                    "This formal clue duplicates an earlier clue.",
                    "Duplicate constraints add presentation noise without new information.",
                    "Remove the duplicate unless it is intentionally instructional.",
                )
            )
        predicate_hashes.add(predicate_hash)

    if has_numeric_template and (
        anchor is None
        or not anchor.items
        or any(item.numeric_value is None for item in anchor.items)
    ):
        messages.append(
            _message(
                BuilderMessageLevel.INVALID,
                "clues",
                "A numeric-difference clue lacks complete anchor values.",
                "Exact difference semantics require one numeric value for every anchor row.",
                "Complete the anchor numeric values or replace the numeric clue.",
            )
        )
    return tuple(messages)


def _ids(
    draft: LogicGridBuilderDraft,
) -> tuple[
    dict[str, str],
    dict[tuple[str, str], str],
    dict[tuple[str, str], str],
]:
    category_ids = {
        category.category_key: (
            f"deductra:category:logic-grid:user:{draft.draft_id}:{category.category_key}"
        )
        for category in draft.categories
    }
    value_ids = {
        (category.category_key, item.item_key): (
            f"deductra:value:logic-grid:user:{draft.draft_id}:"
            f"{category.category_key}:{item.item_key}"
        )
        for category in draft.categories
        for item in category.items
    }
    variable_ids = {
        (category.category_key, item.item_key): (
            f"deductra:variable:logic-grid:user:{draft.draft_id}:"
            f"{category.category_key}:{item.item_key}"
        )
        for category in draft.categories
        for item in category.items
    }
    return category_ids, value_ids, variable_ids


def _compile_predicate(
    predicate: BuilderPredicate,
    variable_ids: Mapping[tuple[str, str], str],
) -> BooleanExpression:
    def variable(ref: BuilderItemRef) -> VariableReference:
        return VariableReference(variable_id=variable_ids[(ref.category_key, ref.item_key)])

    if isinstance(predicate, AssociationTemplate):
        relation = Equal if predicate.relation == "same" else NotEqual
        return relation(left=variable(predicate.left), right=variable(predicate.right))
    if isinstance(predicate, OrderingTemplate):
        return LessThan(left=variable(predicate.earlier), right=variable(predicate.later))
    if isinstance(predicate, NumericDifferenceTemplate):
        return Equal(
            left=Subtract(left=variable(predicate.greater), right=variable(predicate.lesser)),
            right=Constant(value=predicate.difference),
        )
    if isinstance(predicate, AllTemplate):
        return And(
            operands=tuple(_compile_predicate(item, variable_ids) for item in predicate.operands)
        )
    if isinstance(predicate, AnyTemplate):
        return Or(
            operands=tuple(_compile_predicate(item, variable_ids) for item in predicate.operands)
        )
    if isinstance(predicate, NegationTemplate):
        return Not(operand=_compile_predicate(predicate.operand, variable_ids))
    if isinstance(predicate, ExclusiveTemplate):
        return Xor(
            left=_compile_predicate(predicate.left, variable_ids),
            right=_compile_predicate(predicate.right, variable_ids),
        )
    if isinstance(predicate, ConditionalTemplate):
        return Implies(
            premise=_compile_predicate(predicate.premise, variable_ids),
            conclusion=_compile_predicate(predicate.conclusion, variable_ids),
        )
    if isinstance(predicate, EquivalentTemplate):
        return Equivalent(
            left=_compile_predicate(predicate.left, variable_ids),
            right=_compile_predicate(predicate.right, variable_ids),
        )
    return Cardinality(
        operands=tuple(_compile_predicate(item, variable_ids) for item in predicate.operands),
        minimum=predicate.minimum,
        maximum=predicate.maximum,
    )


def _render_predicate(
    predicate: BuilderPredicate,
    labels: Mapping[tuple[str, str], str],
) -> str:
    def label(ref: BuilderItemRef) -> str:
        return labels[(ref.category_key, ref.item_key)]

    if isinstance(predicate, AssociationTemplate):
        relation = (
            "is associated with" if predicate.relation == "same" else "is not associated with"
        )
        return f"{label(predicate.left)} {relation} {label(predicate.right)}"
    if isinstance(predicate, OrderingTemplate):
        return f"{label(predicate.earlier)} is before {label(predicate.later)}"
    if isinstance(predicate, NumericDifferenceTemplate):
        return (
            f"{label(predicate.greater)} has an anchor value exactly "
            f"{predicate.difference} greater than {label(predicate.lesser)}"
        )
    if isinstance(predicate, AllTemplate):
        rendered = tuple(_render_predicate(item, labels) for item in predicate.operands)
        return "All of these are true: " + "; ".join(rendered)
    if isinstance(predicate, AnyTemplate):
        rendered = tuple(_render_predicate(item, labels) for item in predicate.operands)
        return "At least one of these is true: " + "; ".join(rendered)
    if isinstance(predicate, NegationTemplate):
        return f"It is not the case that {_render_predicate(predicate.operand, labels)}"
    if isinstance(predicate, ExclusiveTemplate):
        return (
            f"Exactly one is true: {_render_predicate(predicate.left, labels)}; or "
            f"{_render_predicate(predicate.right, labels)}"
        )
    if isinstance(predicate, ConditionalTemplate):
        return (
            f"If {_render_predicate(predicate.premise, labels)}, then "
            f"{_render_predicate(predicate.conclusion, labels)}"
        )
    if isinstance(predicate, EquivalentTemplate):
        return (
            f"{_render_predicate(predicate.left, labels)} if and only if "
            f"{_render_predicate(predicate.right, labels)}"
        )
    rendered = tuple(_render_predicate(item, labels) for item in predicate.operands)
    return f"Between {predicate.minimum} and {predicate.maximum} of these are true: " + "; ".join(
        rendered
    )


def _compile(draft: LogicGridBuilderDraft) -> tuple[LogicGridSpec, tuple[str, ...]]:
    category_ids, value_ids, variable_ids = _ids(draft)
    anchor = next(
        category
        for category in draft.categories
        if category.category_key == draft.anchor_category_key
    )
    anchor_domain_id = f"deductra:domain:logic-grid:user:{draft.draft_id}:{anchor.category_key}"
    domains = tuple(
        Domain(
            domain_id=f"deductra:domain:logic-grid:user:{draft.draft_id}:{category.category_key}",
            values=tuple(
                DomainValue(
                    value_id=value_ids[(category.category_key, item.item_key)],
                    label=item.label.strip(),
                    ordinal=index if category is anchor else None,
                    numeric_value=item.numeric_value if category is anchor else None,
                )
                for index, item in enumerate(category.items, start=1)
            ),
            ordered=category is anchor,
            distinct_by_default=True,
        )
        for category in draft.categories
    )
    categories = tuple(
        LogicGridCategory(
            category_id=category_ids[category.category_key],
            label=category.label.strip(),
            domain_id=f"deductra:domain:logic-grid:user:{draft.draft_id}:{category.category_key}",
            variable_ids=tuple(
                variable_ids[(category.category_key, item.item_key)] for item in category.items
            ),
        )
        for category in draft.categories
    )
    variables = tuple(
        Variable(
            variable_id=variable_ids[(category.category_key, item.item_key)],
            label=item.label.strip(),
            domain_id=anchor_domain_id,
            role="entity_assignment",
        )
        for category in draft.categories
        for item in category.items
    )
    bijections = tuple(
        AllDifferentConstraint(
            constraint_id=(
                f"deductra:constraint:logic-grid:user:{draft.draft_id}:"
                f"{category.category_key}:bijection"
            ),
            label=f"Each {category.label.strip().lower()} item occupies a different row",
            variable_ids=tuple(
                variable_ids[(category.category_key, item.item_key)] for item in category.items
            ),
        )
        for category in draft.categories
    )
    labels = {
        (category.category_key, item.item_key): item.label.strip()
        for category in draft.categories
        for item in category.items
    }
    clue_texts = tuple(
        clue.text.strip()
        if clue.text is not None
        else _render_predicate(clue.predicate, labels) + "."
        for clue in draft.clues
    )
    clue_constraints = tuple(
        ArithmeticConstraint(
            constraint_id=f"deductra:constraint:logic-grid:user:{draft.draft_id}:{clue.clue_key}",
            label=clue_text.rstrip("."),
            source_clue_id=f"deductra:clue:logic-grid:user:{draft.draft_id}:{clue.clue_key}",
            expression=_compile_predicate(clue.predicate, variable_ids),
        )
        for clue, clue_text in zip(draft.clues, clue_texts, strict=True)
    )
    clues = tuple(
        Clue(
            clue_id=f"deductra:clue:logic-grid:user:{draft.draft_id}:{clue.clue_key}",
            text=clue_text,
            constraint_ids=(
                f"deductra:constraint:logic-grid:user:{draft.draft_id}:{clue.clue_key}",
            ),
            locale=draft.locale,
            template_id=f"logic-grid-builder:{clue.predicate.kind}:1",
        )
        for clue, clue_text in zip(draft.clues, clue_texts, strict=True)
    )
    puzzle = LogicGridSpec(
        identity=PuzzleIdentity(
            puzzle_id=f"deductra:puzzle:logic-grid:user:{draft.draft_id}",
            revision_id=(f"deductra:revision:logic-grid:user:{draft.draft_id}:{draft.revision}"),
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title=draft.title.strip(),
            author=draft.author.strip() if draft.author is not None else None,
            source_kind="user",
            created_at=draft.created_at,
            metadata={
                "builder_schema_version": BUILDER_SCHEMA_VERSION,
                "dimensions": f"{len(anchor.items)}x{len(draft.categories)}",
            },
        ),
        domains=domains,
        variables=variables,
        constraints=(*bijections, *clue_constraints),
        clues=clues,
        givens=tuple(
            AssignmentAtom(
                variable_id=variable_ids[(anchor.category_key, item.item_key)],
                value_id=value_ids[(anchor.category_key, item.item_key)],
            )
            for item in anchor.items
        ),
        display_spec=DisplaySpec(
            locale=draft.locale,
            accessibility_labels=tuple(
                (variable.variable_id, variable.label) for variable in variables
            ),
        ),
        provenance=ProvenanceBundle(
            references=(
                ProvenanceReference(
                    provenance_id=f"deductra:provenance:logic-grid:user:{draft.draft_id}:builder",
                    kind="activity",
                    label="Created through the Deductra Logic Grid guided builder",
                ),
            )
        ),
        categories=categories,
        anchor_category_id=category_ids[anchor.category_key],
    )
    return puzzle, clue_texts


def _preview(
    draft: LogicGridBuilderDraft,
    puzzle: LogicGridSpec,
    clue_texts: tuple[str, ...],
) -> LogicGridBuilderPreview:
    anchor = next(
        category
        for category in draft.categories
        if category.category_key == draft.anchor_category_key
    )
    category_table = tuple(
        (category.label.strip(), tuple(item.label.strip() for item in category.items))
        for category in draft.categories
    )
    return LogicGridBuilderPreview(
        title=puzzle.identity.title,
        dimensions=f"{len(anchor.items)}x{len(draft.categories)}",
        anchor_category=anchor.label.strip(),
        category_table=category_table,
        association_grid=tuple(
            (
                item.label.strip(),
                tuple(
                    category.label.strip()
                    for category in draft.categories
                    if category is not anchor
                ),
            )
            for item in anchor.items
        ),
        clue_texts=clue_texts,
        variable_count=len(puzzle.variables),
        constraint_count=len(puzzle.constraints),
        puzzle_spec_hash=canonical_sha256(puzzle),
    )


def _proof(
    puzzle: LogicGridSpec, draft_hash: str
) -> tuple[
    LogicGridBuilderProof | None,
    BuilderValidationMessage | None,
]:
    source = create_initial_state(
        puzzle,
        state_id=f"deductra:state:logic-grid-builder:{draft_hash}:initial",
        branch_id=f"deductra:branch:logic-grid-builder:{draft_hash}:root",
        sequence_no=0,
    )
    engine = HumanReasoningEngine(
        logic_grid_rules(),
        VerifiedRuleAuthority(
            CrossVerificationCoordinator((Z3ProofBackend(), CpSatProofBackend()))
        ),
    )
    context = HumanSolveContext(
        trace_id=f"deductra:trace:logic-grid-builder:{draft_hash}",
        correlation_id=f"deductra:correlation:logic-grid-builder:{draft_hash}",
        producer=ProducerRef(
            producer_id="deductra:producer:logic-grid-builder-validator",
            kind="tool",
            version=BUILDER_SCHEMA_VERSION,
        ),
        occurred_at=puzzle.identity.created_at,
        previous_event_hash=GENESIS_EVENT_HASH,
    )
    trace = engine.solve(puzzle, source, context)
    if trace.status is not HumanSolveStatus.SOLVED:
        return None, _message(
            BuilderMessageLevel.UNPROVEN,
            "proof",
            f"Verified human reasoning ended with status '{trace.status.value}'.",
            "The current clues do not yet establish a complete solution through disclosed rules.",
            "Add or revise clues, then run the proof check again.",
        )
    final_state = source
    for event in trace.events:
        final_state = reduce_state(final_state, event)
    solution = tuple(
        AssignmentAtom(
            variable_id=variable.variable_id,
            value_id=next(iter(final_state.candidate_domains[variable.variable_id])),
        )
        for variable in puzzle.variables
    )
    check = check_logic_grid_solution(puzzle, solution)
    if not check.accepted:
        return None, _message(
            BuilderMessageLevel.INVALID,
            "proof",
            "The completed reasoning trace failed independent final checking.",
            f"Final-solution violations were: {', '.join(check.violations)}.",
            "Do not save this revision; inspect the family implementation and clues.",
        )
    certificate_ids = tuple(
        certificate_id for attempt in trace.attempts for certificate_id in attempt.certificate_ids
    )
    return (
        LogicGridBuilderProof(
            human_solvable=True,
            unique=True,
            trace_hash=trace.trace_hash,
            final_state_hash=final_state.state_hash,
            verified_steps=len(trace.events),
            certificate_ids=certificate_ids,
            solution=solution,
        ),
        None,
    )


def assess_logic_grid_builder(
    draft: LogicGridBuilderDraft,
    *,
    verify: bool = False,
) -> LogicGridBuilderAssessment:
    """Validate, preview, compile, and optionally prove one guided draft."""
    draft_hash = canonical_sha256(draft)
    messages = list(_validate_draft(draft))
    if any(item.level is BuilderMessageLevel.INVALID for item in messages):
        return LogicGridBuilderAssessment(
            draft_hash=draft_hash,
            status=BuilderStatus.INVALID,
            stage=BuilderStage.CATEGORIES if draft.categories else BuilderStage.PROFILE,
            messages=tuple(messages),
        )
    if any(item.level is BuilderMessageLevel.INCOMPLETE for item in messages):
        stage = (
            BuilderStage.PROFILE
            if not draft.title.strip()
            else BuilderStage.CATEGORIES
            if len(draft.categories) < 3
            or any(len(category.items) < 2 for category in draft.categories)
            or not draft.anchor_category_key
            else BuilderStage.CLUES
        )
        return LogicGridBuilderAssessment(
            draft_hash=draft_hash,
            status=BuilderStatus.INCOMPLETE,
            stage=stage,
            messages=tuple(messages),
        )

    puzzle, clue_texts = _compile(draft)
    preview = _preview(draft, puzzle, clue_texts)
    if not verify:
        messages.append(
            _message(
                BuilderMessageLevel.UNPROVEN,
                "proof",
                "Solvability and uniqueness have not been checked.",
                "Structural validity alone does not establish a playable puzzle.",
                "Run the verified proof check before saving or playing this revision.",
            )
        )
        return LogicGridBuilderAssessment(
            draft_hash=draft_hash,
            status=BuilderStatus.UNPROVEN,
            stage=BuilderStage.PREVIEW,
            messages=tuple(messages),
            preview=preview,
            puzzle=puzzle,
        )

    proof, proof_message = _proof(puzzle, draft_hash)
    if proof_message is not None:
        messages.append(proof_message)
        return LogicGridBuilderAssessment(
            draft_hash=draft_hash,
            status=(
                BuilderStatus.INVALID
                if proof_message.level is BuilderMessageLevel.INVALID
                else BuilderStatus.UNPROVEN
            ),
            stage=BuilderStage.PROOF,
            messages=tuple(messages),
            preview=preview,
            puzzle=puzzle,
        )
    return LogicGridBuilderAssessment(
        draft_hash=draft_hash,
        status=(
            BuilderStatus.WARNING
            if any(item.level is BuilderMessageLevel.WARNING for item in messages)
            else BuilderStatus.VALID
        ),
        stage=BuilderStage.READY,
        messages=tuple(messages),
        preview=preview,
        puzzle=puzzle,
        proof=proof,
    )


def rendered_logic_grid_builder_preview(assessment: LogicGridBuilderAssessment) -> str:
    """Return a deterministic plain-text preview for CLI and terminal adapters."""
    if assessment.preview is None:
        return "\n".join(
            f"[{message.level.value}] {message.path}: {message.problem} {message.correction}"
            for message in assessment.messages
        )
    preview = assessment.preview
    lines = [
        preview.title,
        f"Status: {assessment.status.value}",
        f"Shape: {preview.dimensions}; anchor: {preview.anchor_category}",
        "Categories:",
    ]
    lines.extend(f"- {label}: {', '.join(items)}" for label, items in preview.category_table)
    lines.append("Clues:")
    lines.extend(f"{index}. {text}" for index, text in enumerate(preview.clue_texts, start=1))
    lines.append(
        f"Formal model: {preview.variable_count} variables, {preview.constraint_count} constraints"
    )
    lines.append(f"Fingerprint: {preview.puzzle_spec_hash}")
    if assessment.messages:
        lines.append("Validation:")
        lines.extend(
            f"- [{message.level.value}] {message.path}: {message.problem} {message.correction}"
            for message in assessment.messages
        )
    return "\n".join(lines) + "\n"
