"""Acceptance tests for the FAM-LE-001 Logic Equations specification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    Constant,
    Equal,
    Equivalent,
    GreaterThan,
    Implies,
    VariableReference,
)
from deductra.domain.puzzle import (
    Clue,
    DisplaySpec,
    ProvenanceBundle,
    PuzzleIdentity,
)
from deductra.domain.serialization import canonical_sha256
from deductra.domain.values import Domain, DomainValue, Variable
from deductra.families.logic_equations import (
    FAMILY_ID,
    SPEC_SCHEMA_VERSION,
    LogicEquationsSpec,
    logic_equations_spec_json_schema,
    rendered_logic_equations_spec_json_schema,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def logic_equations_spec() -> LogicEquationsSpec:
    """Build a small specification fixture that is not a Golden puzzle."""
    domain_id = "deductra:domain:logic-equations-example"
    variables = tuple(
        Variable(
            variable_id=f"deductra:variable:{label.lower()}",
            label=label,
            domain_id=domain_id,
            role="arithmetic",
        )
        for label in ("A", "B", "C")
    )
    all_different_id = "deductra:constraint:all-different"
    clue_constraint_id = "deductra:constraint:a-is-one"
    return LogicEquationsSpec(
        identity=PuzzleIdentity(
            puzzle_id="deductra:puzzle:logic-equations-spec-fixture",
            revision_id="deductra:revision:logic-equations-spec-fixture:1",
            family_id=FAMILY_ID,
            schema_version=SPEC_SCHEMA_VERSION,
            title="Specification fixture",
            source_kind="user",
            created_at=datetime(2026, 7, 16, tzinfo=UTC),
        ),
        domains=(
            Domain(
                domain_id=domain_id,
                values=tuple(
                    DomainValue(
                        value_id=f"deductra:value:{value}",
                        label=str(value),
                        ordinal=value,
                        numeric_value=value,
                    )
                    for value in range(1, 4)
                ),
                ordered=True,
                distinct_by_default=True,
            ),
        ),
        variables=variables,
        constraints=(
            AllDifferentConstraint(
                constraint_id=all_different_id,
                label="Every variable has a different value",
                variable_ids=tuple(variable.variable_id for variable in variables),
            ),
            ArithmeticConstraint(
                constraint_id=clue_constraint_id,
                label="A equals one",
                source_clue_id="deductra:clue:a-is-one",
                expression=Equal(
                    left=VariableReference(variable_id="deductra:variable:a"),
                    right=Constant(value=1),
                ),
            ),
        ),
        clues=(
            Clue(
                clue_id="deductra:clue:a-is-one",
                text="A equals 1.",
                constraint_ids=(clue_constraint_id,),
                locale="en",
            ),
        ),
        givens=(),
        display_spec=DisplaySpec(),
        provenance=ProvenanceBundle(),
    )


def test_specification_round_trip_preserves_canonical_identity() -> None:
    original = logic_equations_spec()
    restored = LogicEquationsSpec.model_validate_json(original.model_dump_json())
    assert restored == original
    assert canonical_sha256(restored) == canonical_sha256(original)


def test_family_and_schema_identity_are_fixed() -> None:
    payload = logic_equations_spec().model_dump()
    payload["identity"]["family_id"] = "another-family"
    with pytest.raises(ValidationError, match="family_id must be"):
        LogicEquationsSpec.model_validate(payload)

    payload = logic_equations_spec().model_dump()
    payload["identity"]["schema_version"] = "2.0.0"
    with pytest.raises(ValidationError, match="schema_version must be"):
        LogicEquationsSpec.model_validate(payload)


def test_domain_is_the_ordered_integer_permutation_one_through_n() -> None:
    payload = logic_equations_spec().model_dump()
    payload["domains"][0]["values"][1]["numeric_value"] = 4
    with pytest.raises(ValidationError, match=r"ordered range 1\.\.n"):
        LogicEquationsSpec.model_validate(payload)


def test_all_different_constraint_covers_every_variable_once() -> None:
    payload = logic_equations_spec().model_dump()
    payload["constraints"][0]["variable_ids"] = (
        "deductra:variable:a",
        "deductra:variable:b",
    )
    with pytest.raises(ValidationError, match="cover every variable"):
        LogicEquationsSpec.model_validate(payload)


def test_expression_references_must_be_closed_over_the_specification() -> None:
    payload = logic_equations_spec().model_dump()
    payload["constraints"][1]["expression"]["left"]["variable_id"] = "deductra:variable:unknown"
    with pytest.raises(ValidationError, match="unknown variable"):
        LogicEquationsSpec.model_validate(payload)


def test_constraint_provenance_must_match_the_linked_clue() -> None:
    payload = logic_equations_spec().model_dump()
    payload["constraints"][1]["source_clue_id"] = "deductra:clue:unknown"
    with pytest.raises(ValidationError, match="source_clue_id values must match"):
        LogicEquationsSpec.model_validate(payload)


def test_v1_accepts_conditionals_and_rejects_unlisted_boolean_forms() -> None:
    original = logic_equations_spec()
    conditional = Implies(
        premise=Equal(
            left=VariableReference(variable_id="deductra:variable:a"),
            right=Constant(value=1),
        ),
        conclusion=GreaterThan(
            left=VariableReference(variable_id="deductra:variable:b"),
            right=Constant(value=1),
        ),
    )
    accepted = original.model_copy(
        update={
            "constraints": (
                original.constraints[0],
                ArithmeticConstraint(
                    constraint_id="deductra:constraint:a-is-one",
                    label="Conditional",
                    source_clue_id="deductra:clue:a-is-one",
                    expression=conditional,
                ),
            )
        }
    )
    assert LogicEquationsSpec.model_validate(accepted.model_dump())

    unsupported = Equivalent(left=conditional.premise, right=conditional.conclusion)
    payload = original.model_dump()
    payload["constraints"][1]["expression"] = unsupported.model_dump()
    with pytest.raises(ValidationError, match="unsupported Logic Equations expression"):
        LogicEquationsSpec.model_validate(payload)


def test_family_schema_has_a_stable_public_identity() -> None:
    schema = logic_equations_spec_json_schema()
    assert schema["$id"] == "urn:deductra:schema:logic-equations-spec:1"
    assert schema["title"] == "Deductra Logic Equations Specification v1"
    identity = schema["$defs"]["PuzzleIdentity"]["properties"]
    assert identity["family_id"]["const"] == FAMILY_ID
    assert identity["schema_version"]["const"] == SPEC_SCHEMA_VERSION


def test_checked_in_family_schema_is_current() -> None:
    schema_path = REPOSITORY_ROOT / "schemas" / "logic-equations-spec-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == (rendered_logic_equations_spec_json_schema())
