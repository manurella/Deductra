"""Logic Grid specialization of the common immutable puzzle contract."""

from __future__ import annotations

from pydantic import model_validator

from deductra.domain.atoms import AssignmentAtom, ExclusionAtom
from deductra.domain.base import DomainModel
from deductra.domain.constraints import AllDifferentConstraint, ArithmeticConstraint
from deductra.domain.expressions import (
    And,
    BooleanExpression,
    Cardinality,
    Constant,
    Equal,
    Equivalent,
    GreaterThan,
    GreaterThanOrEqual,
    Implies,
    LessThan,
    LessThanOrEqual,
    Not,
    NotEqual,
    NumericExpression,
    Or,
    Subtract,
    VariableReference,
    Xor,
)
from deductra.domain.ids import DomainId, Identifier, VariableId
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.values import Domain

FAMILY_ID = "logic-grid"
SPEC_SCHEMA_VERSION = "1.0.0"


class LogicGridCategory(DomainModel):
    """One named item category and its aligned assignment variables."""

    category_id: Identifier
    label: str
    domain_id: DomainId
    variable_ids: tuple[VariableId, ...]


class LogicGridSpec(PuzzleSpec):
    """An unordered one-to-one association puzzle over aligned categories."""

    categories: tuple[LogicGridCategory, ...]
    anchor_category_id: Identifier

    @model_validator(mode="after")
    def validate_logic_grid_contract(self) -> LogicGridSpec:
        """Enforce the normalized v1 family specification."""
        if self.identity.family_id != FAMILY_ID:
            raise ValueError(f"family_id must be {FAMILY_ID!r}")
        if self.identity.schema_version != SPEC_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SPEC_SCHEMA_VERSION!r}")
        if len(self.categories) < 3:
            raise ValueError("Logic Grid requires at least three categories")

        category_ids = tuple(category.category_id for category in self.categories)
        if len(category_ids) != len(set(category_ids)):
            raise ValueError("category identifiers must be unique")
        labels = tuple(category.label.strip() for category in self.categories)
        if any(not label for label in labels) or len(labels) != len(set(labels)):
            raise ValueError("category labels must be non-empty and unique")
        if self.anchor_category_id not in set(category_ids):
            raise ValueError("anchor_category_id must reference a declared category")

        domains_by_id = {domain.domain_id: domain for domain in self.domains}
        category_domain_ids = tuple(category.domain_id for category in self.categories)
        if len(category_domain_ids) != len(set(category_domain_ids)):
            raise ValueError("each category must reference a different domain")
        if set(category_domain_ids) != set(domains_by_id):
            raise ValueError("categories must cover every domain exactly once")

        category_size = len(domains_by_id[category_domain_ids[0]].values)
        if category_size < 2:
            raise ValueError("each category must contain at least two items")
        if any(
            len(domains_by_id[domain_id].values) != category_size
            for domain_id in category_domain_ids
        ):
            raise ValueError("all Logic Grid categories must have the same size")
        if any(
            not domains_by_id[domain_id].distinct_by_default for domain_id in category_domain_ids
        ):
            raise ValueError("every category domain must be distinct by default")

        value_ids = tuple(value.value_id for domain in self.domains for value in domain.values)
        if len(value_ids) != len(set(value_ids)):
            raise ValueError("item value identifiers must be globally unique")
        for domain in self.domains:
            item_labels = tuple(value.label.strip() for value in domain.values)
            if any(not label for label in item_labels) or len(item_labels) != len(set(item_labels)):
                raise ValueError("item labels must be non-empty and unique within a category")

        variables_by_id = {variable.variable_id: variable for variable in self.variables}
        declared_variable_ids = tuple(
            variable_id for category in self.categories for variable_id in category.variable_ids
        )
        if len(declared_variable_ids) != len(set(declared_variable_ids)):
            raise ValueError("category variable references must be unique")
        if set(declared_variable_ids) != set(variables_by_id):
            raise ValueError("categories must partition every variable exactly once")
        if any(len(category.variable_ids) != category_size for category in self.categories):
            raise ValueError("each category requires one variable for each item")

        anchor_category = next(
            category
            for category in self.categories
            if category.category_id == self.anchor_category_id
        )
        anchor_domain = domains_by_id[anchor_category.domain_id]
        if any(
            variable.domain_id != anchor_domain.domain_id or variable.role != "entity_assignment"
            for variable in self.variables
        ):
            raise ValueError(
                "all Logic Grid variables must be entity assignments over the anchor domain"
            )

        for category in self.categories:
            domain = domains_by_id[category.domain_id]
            for variable_id, value in zip(category.variable_ids, domain.values, strict=True):
                if variables_by_id[variable_id].label != value.label:
                    raise ValueError(
                        "category variable order and labels must align with domain values"
                    )

        self._validate_anchor_domain(anchor_domain)
        variable_id_set = frozenset(variables_by_id)
        self._validate_constraints(variable_id_set)
        self._validate_clues()
        self._validate_givens(anchor_category, anchor_domain)
        return self

    @staticmethod
    def _validate_anchor_domain(anchor_domain: Domain) -> None:
        if anchor_domain.ordered:
            expected_ordinals = tuple(range(1, len(anchor_domain.values) + 1))
            ordinals = tuple(value.ordinal for value in anchor_domain.values)
            if ordinals != expected_ordinals:
                raise ValueError("an ordered anchor domain must use ordinals 1..n")
        numeric_values = tuple(value.numeric_value for value in anchor_domain.values)
        if any(value is not None for value in numeric_values):
            if any(value is None for value in numeric_values):
                raise ValueError("anchor numeric values must be either complete or absent")
            if len(numeric_values) != len(set(numeric_values)):
                raise ValueError("anchor numeric values must be unique")

    def _validate_constraints(self, variable_ids: frozenset[VariableId]) -> None:
        all_different = tuple(
            constraint
            for constraint in self.constraints
            if isinstance(constraint, AllDifferentConstraint)
        )
        arithmetic = tuple(
            constraint
            for constraint in self.constraints
            if isinstance(constraint, ArithmeticConstraint)
        )
        if len(all_different) + len(arithmetic) != len(self.constraints):
            raise ValueError(
                "Logic Grid constraints must be all-different or arithmetic constraints"
            )
        if len(all_different) != len(self.categories):
            raise ValueError("each category requires exactly one all-different constraint")

        expected_groups = {frozenset(category.variable_ids) for category in self.categories}
        actual_groups: set[frozenset[VariableId]] = set()
        for constraint in all_different:
            group = frozenset(constraint.variable_ids)
            if (
                len(group) != len(constraint.variable_ids)
                or group not in expected_groups
                or constraint.source_clue_id is not None
            ):
                raise ValueError("all-different constraints must cover each category exactly once")
            actual_groups.add(group)
        if actual_groups != expected_groups:
            raise ValueError("all-different constraints must cover each category exactly once")
        if not arithmetic:
            raise ValueError("Logic Grid requires at least one clue constraint")

        anchor_category = next(
            category
            for category in self.categories
            if category.category_id == self.anchor_category_id
        )
        anchor_domain = next(
            domain for domain in self.domains if domain.domain_id == anchor_category.domain_id
        )
        for constraint in arithmetic:
            self._validate_boolean_expression(
                constraint.expression,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            if not self._referenced_variables(constraint.expression):
                raise ValueError("a Logic Grid clue expression must reference an item variable")

    def _validate_clues(self) -> None:
        arithmetic = {
            constraint.constraint_id: constraint
            for constraint in self.constraints
            if isinstance(constraint, ArithmeticConstraint)
        }
        referenced_ids: set[str] = set()
        clue_ids = {clue.clue_id for clue in self.clues}
        for clue in self.clues:
            if not clue.text.strip() or not clue.constraint_ids:
                raise ValueError("each clue must contain text and reference a constraint")
            if len(clue.constraint_ids) != len(set(clue.constraint_ids)):
                raise ValueError("a clue cannot repeat a constraint reference")
            unknown = set(clue.constraint_ids) - set(arithmetic)
            if unknown:
                raise ValueError("clues may reference only arithmetic clue constraints")
            referenced_ids.update(clue.constraint_ids)
        if referenced_ids != set(arithmetic):
            raise ValueError("clues must cover every arithmetic constraint")
        if any(
            constraint.source_clue_id not in clue_ids
            or constraint.constraint_id
            not in next(
                clue.constraint_ids
                for clue in self.clues
                if clue.clue_id == constraint.source_clue_id
            )
            for constraint in arithmetic.values()
        ):
            raise ValueError("constraint provenance must match a supporting clue")

    def _validate_givens(
        self,
        anchor_category: LogicGridCategory,
        anchor_domain: Domain,
    ) -> None:
        variable_ids = {variable.variable_id for variable in self.variables}
        anchor_value_ids = {value.value_id for value in anchor_domain.values}
        normalized: set[tuple[str, str, str]] = set()
        assignments: dict[str, str] = {}
        exclusions: set[tuple[str, str]] = set()
        for given in self.givens:
            if not isinstance(given, (AssignmentAtom, ExclusionAtom)):
                raise ValueError("Logic Grid givens must be assignments or exclusions")
            if given.variable_id not in variable_ids or given.value_id not in anchor_value_ids:
                raise ValueError("givens must reference variables and anchor values in this puzzle")
            key = (given.kind, given.variable_id, given.value_id)
            if key in normalized:
                raise ValueError("givens cannot contain duplicate atoms")
            normalized.add(key)
            if isinstance(given, AssignmentAtom):
                previous = assignments.setdefault(given.variable_id, given.value_id)
                if previous != given.value_id:
                    raise ValueError("a variable cannot be assigned two anchor values")
            else:
                exclusions.add((given.variable_id, given.value_id))

        if any(
            (variable_id, value_id) in exclusions for variable_id, value_id in assignments.items()
        ):
            raise ValueError("a given assignment cannot also be excluded")
        for category in self.categories:
            assigned_values = [
                assignments[variable_id]
                for variable_id in category.variable_ids
                if variable_id in assignments
            ]
            if len(assigned_values) != len(set(assigned_values)):
                raise ValueError("given assignments must respect category bijections")

        required_anchor_assignments = {
            variable_id: value.value_id
            for variable_id, value in zip(
                anchor_category.variable_ids,
                anchor_domain.values,
                strict=True,
            )
        }
        if any(
            assignments.get(variable_id) != value_id
            for variable_id, value_id in required_anchor_assignments.items()
        ):
            raise ValueError(
                "anchor category variables must be assigned to their aligned anchor values"
            )

    @classmethod
    def _validate_boolean_expression(
        cls,
        expression: BooleanExpression,
        variable_ids: frozenset[VariableId],
        *,
        anchor_domain: Domain,
    ) -> None:
        if isinstance(expression, (Equal, NotEqual)):
            cls._validate_numeric_expression(
                expression.left,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            cls._validate_numeric_expression(
                expression.right,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            if not (
                isinstance(expression.left, VariableReference)
                and isinstance(expression.right, VariableReference)
            ) and not cls._has_complete_numeric_values(anchor_domain):
                raise ValueError(
                    "numeric Logic Grid expressions require complete anchor numeric values"
                )
            return
        if isinstance(
            expression,
            (LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
        ):
            if not anchor_domain.ordered:
                raise ValueError("ordered comparisons require an ordered anchor category")
            cls._validate_numeric_expression(
                expression.left,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            cls._validate_numeric_expression(
                expression.right,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            return
        if isinstance(expression, (And, Or)):
            for operand in expression.operands:
                cls._validate_boolean_expression(
                    operand,
                    variable_ids,
                    anchor_domain=anchor_domain,
                )
            return
        if isinstance(expression, Not):
            cls._validate_boolean_expression(
                expression.operand,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            return
        if isinstance(expression, (Xor, Equivalent)):
            cls._validate_boolean_expression(
                expression.left,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            cls._validate_boolean_expression(
                expression.right,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            return
        if isinstance(expression, Implies):
            cls._validate_boolean_expression(
                expression.premise,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            cls._validate_boolean_expression(
                expression.conclusion,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            return
        if isinstance(expression, Cardinality):
            for operand in expression.operands:
                cls._validate_boolean_expression(
                    operand,
                    variable_ids,
                    anchor_domain=anchor_domain,
                )
            return
        raise ValueError(f"unsupported Logic Grid expression: {expression.kind}")

    @classmethod
    def _validate_numeric_expression(
        cls,
        expression: NumericExpression,
        variable_ids: frozenset[VariableId],
        *,
        anchor_domain: Domain,
    ) -> None:
        if isinstance(expression, VariableReference):
            if expression.variable_id not in variable_ids:
                raise ValueError(
                    f"expression references unknown variable: {expression.variable_id}"
                )
            return
        if isinstance(expression, Constant):
            if isinstance(expression.value, bool) or not cls._has_complete_numeric_values(
                anchor_domain
            ):
                raise ValueError("Logic Grid constants require complete numeric anchor values")
            return
        if isinstance(expression, Subtract):
            if not cls._has_complete_numeric_values(anchor_domain):
                raise ValueError(
                    "numeric Logic Grid expressions require complete anchor numeric values"
                )
            cls._validate_numeric_expression(
                expression.left,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            cls._validate_numeric_expression(
                expression.right,
                variable_ids,
                anchor_domain=anchor_domain,
            )
            return
        raise ValueError(f"unsupported Logic Grid numeric expression: {expression.kind}")

    @staticmethod
    def _has_complete_numeric_values(anchor_domain: Domain) -> bool:
        return all(value.numeric_value is not None for value in anchor_domain.values)

    @classmethod
    def _referenced_variables(
        cls,
        expression: BooleanExpression | NumericExpression,
    ) -> frozenset[VariableId]:
        if isinstance(expression, VariableReference):
            return frozenset((expression.variable_id,))
        if isinstance(expression, Constant):
            return frozenset()
        if isinstance(expression, Subtract):
            return cls._referenced_variables(expression.left) | cls._referenced_variables(
                expression.right
            )
        if isinstance(
            expression,
            (Equal, NotEqual, LessThan, LessThanOrEqual, GreaterThan, GreaterThanOrEqual),
        ):
            return cls._referenced_variables(expression.left) | cls._referenced_variables(
                expression.right
            )
        if isinstance(expression, (And, Or, Cardinality)):
            references: set[VariableId] = set()
            for operand in expression.operands:
                references.update(cls._referenced_variables(operand))
            return frozenset(references)
        if isinstance(expression, Not):
            return cls._referenced_variables(expression.operand)
        if isinstance(expression, (Xor, Equivalent)):
            return cls._referenced_variables(expression.left) | cls._referenced_variables(
                expression.right
            )
        if isinstance(expression, Implies):
            return cls._referenced_variables(expression.premise) | cls._referenced_variables(
                expression.conclusion
            )
        raise ValueError(f"unsupported Logic Grid expression: {expression.kind}")
