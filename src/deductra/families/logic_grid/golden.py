"""Handcrafted reference fixtures for the Logic Grid family."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from deductra.domain.atoms import AssignmentAtom
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import Equal, VariableReference
from deductra.domain.puzzle import (
    Clue,
    DisplaySpec,
    ProvenanceBundle,
    ProvenanceReference,
    PuzzleIdentity,
)
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_grid.specification import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicGridCategory,
    LogicGridSpec,
)


@dataclass(frozen=True)
class _CategoryDefinition:
    slug: str
    label: str
    items: tuple[str, ...]
    solution_rows: tuple[int, ...]


@dataclass(frozen=True)
class _GoldenDefinition:
    slug: str
    title: str
    difficulty: str
    categories: tuple[_CategoryDefinition, ...]


_HARBOR_MORNING = _GoldenDefinition(
    slug="harbor-morning",
    title="Harbor Morning",
    difficulty="easy",
    categories=(
        _CategoryDefinition("visitor", "Visitors", ("Ari", "Bela", "Cora"), (0, 1, 2)),
        _CategoryDefinition("boat", "Boats", ("Kestrel", "Lumen", "Tern"), (1, 2, 0)),
        _CategoryDefinition("drink", "Drinks", ("Cocoa", "Mint Tea", "Cider"), (2, 0, 1)),
    ),
)

_GALLERY_OPENING = _GoldenDefinition(
    slug="gallery-opening",
    title="Gallery Opening",
    difficulty="medium",
    categories=(
        _CategoryDefinition(
            "curator",
            "Curators",
            ("Dara", "Emil", "Farah", "Gio"),
            (0, 1, 2, 3),
        ),
        _CategoryDefinition(
            "exhibit",
            "Exhibits",
            ("Aurora", "Current", "Mosaic", "Stillness"),
            (2, 0, 3, 1),
        ),
        _CategoryDefinition(
            "room",
            "Rooms",
            ("Atrium", "East Hall", "Loft", "West Hall"),
            (1, 3, 0, 2),
        ),
        _CategoryDefinition(
            "refreshment",
            "Refreshments",
            ("Fig Water", "Ginger Fizz", "Lime Soda", "Pear Tonic"),
            (3, 1, 2, 0),
        ),
    ),
)

_OBSERVATORY_ROTATION = _GoldenDefinition(
    slug="observatory-rotation",
    title="Observatory Rotation",
    difficulty="hard",
    categories=(
        _CategoryDefinition(
            "observer",
            "Observers",
            ("Hana", "Ivo", "Jules", "Kei", "Mara"),
            (0, 1, 2, 3, 4),
        ),
        _CategoryDefinition(
            "telescope",
            "Telescopes",
            ("Aster", "Boreal", "Cygnus", "Draco", "Equinox"),
            (3, 0, 4, 1, 2),
        ),
        _CategoryDefinition(
            "target",
            "Targets",
            ("Comet", "Double Star", "Nebula", "Quasar", "Ringed Planet"),
            (1, 4, 2, 0, 3),
        ),
        _CategoryDefinition(
            "notebook",
            "Notebooks",
            ("Amber", "Indigo", "Ivory", "Sage", "Slate"),
            (4, 2, 0, 3, 1),
        ),
        _CategoryDefinition(
            "snack",
            "Snacks",
            ("Almonds", "Berries", "Crackers", "Dates", "Focaccia"),
            (2, 1, 3, 4, 0),
        ),
    ),
)


def _domain_id(definition: _GoldenDefinition, category: _CategoryDefinition) -> str:
    return f"deductra:domain:{definition.slug}:{category.slug}"


def _value_id(definition: _GoldenDefinition, category: _CategoryDefinition, index: int) -> str:
    return f"deductra:value:{definition.slug}:{category.slug}:{index + 1}"


def _variable_id(
    definition: _GoldenDefinition,
    category: _CategoryDefinition,
    index: int,
) -> str:
    return f"deductra:variable:{definition.slug}:{category.slug}:{index + 1}"


def _solution(definition: _GoldenDefinition) -> tuple[AssignmentAtom, ...]:
    anchor = definition.categories[0]
    return tuple(
        AssignmentAtom(
            variable_id=_variable_id(definition, category, item_index),
            value_id=_value_id(definition, anchor, row_index),
        )
        for category in definition.categories
        for item_index, row_index in enumerate(category.solution_rows)
    )


def _build(definition: _GoldenDefinition) -> LogicGridSpec:
    anchor = definition.categories[0]
    size = len(anchor.items)
    domains = tuple(
        Domain(
            domain_id=_domain_id(definition, category),
            values=tuple(
                DomainValue(
                    value_id=_value_id(definition, category, index),
                    label=item,
                    ordinal=index + 1 if category is anchor else None,
                )
                for index, item in enumerate(category.items)
            ),
            ordered=category is anchor,
            distinct_by_default=True,
        )
        for category in definition.categories
    )
    categories = tuple(
        LogicGridCategory(
            category_id=f"deductra:category:{definition.slug}:{category.slug}",
            label=category.label,
            domain_id=_domain_id(definition, category),
            variable_ids=tuple(_variable_id(definition, category, index) for index in range(size)),
        )
        for category in definition.categories
    )
    variables = tuple(
        Variable(
            variable_id=_variable_id(definition, category, index),
            label=item,
            domain_id=_domain_id(definition, anchor),
            role="entity_assignment",
        )
        for category in definition.categories
        for index, item in enumerate(category.items)
    )
    bijections = tuple(
        AllDifferentConstraint(
            constraint_id=f"deductra:constraint:{definition.slug}:{category.slug}:bijection",
            label=f"Each {category.label.lower()} item occupies a different row",
            variable_ids=tuple(_variable_id(definition, category, index) for index in range(size)),
        )
        for category in definition.categories
    )

    clue_constraints: list[ArithmeticConstraint] = []
    clues: list[Clue] = []
    for category in definition.categories[1:]:
        for item_index, row_index in enumerate(category.solution_rows[:-1]):
            item_slug = item_index + 1
            constraint_id = (
                f"deductra:constraint:{definition.slug}:{category.slug}:{item_slug}:match"
            )
            clue_id = f"deductra:clue:{definition.slug}:{category.slug}:{item_slug}:match"
            clue_constraints.append(
                ArithmeticConstraint(
                    constraint_id=constraint_id,
                    label=f"{category.items[item_index]} matches {anchor.items[row_index]}",
                    source_clue_id=clue_id,
                    expression=Equal(
                        left=VariableReference(
                            variable_id=_variable_id(definition, category, item_index)
                        ),
                        right=VariableReference(
                            variable_id=_variable_id(definition, anchor, row_index)
                        ),
                    ),
                )
            )
            clues.append(
                Clue(
                    clue_id=clue_id,
                    text=(
                        f"{category.items[item_index]} was associated with "
                        f"{anchor.items[row_index]}."
                    ),
                    constraint_ids=(constraint_id,),
                    locale="en",
                )
            )

    return LogicGridSpec(
        identity=PuzzleIdentity(
            puzzle_id=f"deductra:puzzle:logic-grid:{definition.slug}",
            revision_id=f"deductra:revision:logic-grid:{definition.slug}:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title=definition.title,
            author="Deductra Project",
            source_kind="golden",
            created_at=datetime(2026, 7, 19, tzinfo=UTC),
            metadata={
                "difficulty": definition.difficulty,
                "dimensions": f"{size}x{size}",
                "golden_version": "1.0.0",
            },
        ),
        domains=domains,
        variables=variables,
        constraints=(*bijections, *clue_constraints),
        clues=tuple(clues),
        givens=tuple(
            AssignmentAtom(
                variable_id=_variable_id(definition, anchor, index),
                value_id=_value_id(definition, anchor, index),
            )
            for index in range(size)
        ),
        display_spec=DisplaySpec(
            accessibility_labels=tuple(
                (variable.variable_id, variable.label) for variable in variables
            )
        ),
        provenance=ProvenanceBundle(
            references=(
                ProvenanceReference(
                    provenance_id=f"deductra:provenance:{definition.slug}:original",
                    kind="entity",
                    label="Original Deductra reference puzzle",
                ),
            )
        ),
        categories=categories,
        anchor_category_id=categories[0].category_id,
    )


HARBOR_MORNING_SOLUTION = _solution(_HARBOR_MORNING)
GALLERY_OPENING_SOLUTION = _solution(_GALLERY_OPENING)
OBSERVATORY_ROTATION_SOLUTION = _solution(_OBSERVATORY_ROTATION)


def harbor_morning() -> LogicGridSpec:
    """Return the fixed 3x3 Easy reference puzzle."""
    return _build(_HARBOR_MORNING)


def gallery_opening() -> LogicGridSpec:
    """Return the fixed 4x4 Medium reference puzzle."""
    return _build(_GALLERY_OPENING)


def observatory_rotation() -> LogicGridSpec:
    """Return the fixed 5x5 Hard reference puzzle."""
    return _build(_OBSERVATORY_ROTATION)


def logic_grid_goldens() -> tuple[LogicGridSpec, LogicGridSpec, LogicGridSpec]:
    """Return the versioned Easy, Medium, and Hard reference triad."""
    return harbor_morning(), gallery_opening(), observatory_rotation()
