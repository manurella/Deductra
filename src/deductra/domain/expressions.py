"""Safe arithmetic and propositional expression trees."""

from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, model_validator

from deductra.domain.base import DomainModel
from deductra.domain.ids import VariableId


class Constant(DomainModel):
    kind: Literal["constant"] = "constant"
    value: int | Fraction | bool


class VariableReference(DomainModel):
    kind: Literal["variable_reference"] = "variable_reference"
    variable_id: VariableId


class Add(DomainModel):
    kind: Literal["add"] = "add"
    operands: tuple[NumericExpression, ...]

    @model_validator(mode="after")
    def require_operands(self) -> Add:
        if len(self.operands) < 2:
            raise ValueError("add requires at least two operands")
        return self


class Subtract(DomainModel):
    kind: Literal["subtract"] = "subtract"
    left: NumericExpression
    right: NumericExpression


class Multiply(DomainModel):
    kind: Literal["multiply"] = "multiply"
    operands: tuple[NumericExpression, ...]

    @model_validator(mode="after")
    def require_operands(self) -> Multiply:
        if len(self.operands) < 2:
            raise ValueError("multiply requires at least two operands")
        return self


class ExactDivide(DomainModel):
    kind: Literal["exact_divide"] = "exact_divide"
    dividend: NumericExpression
    divisor: NumericExpression


class Modulo(DomainModel):
    kind: Literal["modulo"] = "modulo"
    dividend: NumericExpression
    divisor: NumericExpression


class Negate(DomainModel):
    kind: Literal["negate"] = "negate"
    operand: NumericExpression


NumericExpression = Annotated[
    Constant | VariableReference | Add | Subtract | Multiply | ExactDivide | Modulo | Negate,
    Field(discriminator="kind"),
]


class Equal(DomainModel):
    kind: Literal["equal"] = "equal"
    left: NumericExpression
    right: NumericExpression


class NotEqual(DomainModel):
    kind: Literal["not_equal"] = "not_equal"
    left: NumericExpression
    right: NumericExpression


class LessThan(DomainModel):
    kind: Literal["less_than"] = "less_than"
    left: NumericExpression
    right: NumericExpression


class LessThanOrEqual(DomainModel):
    kind: Literal["less_than_or_equal"] = "less_than_or_equal"
    left: NumericExpression
    right: NumericExpression


class GreaterThan(DomainModel):
    kind: Literal["greater_than"] = "greater_than"
    left: NumericExpression
    right: NumericExpression


class GreaterThanOrEqual(DomainModel):
    kind: Literal["greater_than_or_equal"] = "greater_than_or_equal"
    left: NumericExpression
    right: NumericExpression


class And(DomainModel):
    kind: Literal["and"] = "and"
    operands: tuple[BooleanExpression, ...]

    @model_validator(mode="after")
    def require_operands(self) -> And:
        if len(self.operands) < 2:
            raise ValueError("and requires at least two operands")
        return self


class Or(DomainModel):
    kind: Literal["or"] = "or"
    operands: tuple[BooleanExpression, ...]

    @model_validator(mode="after")
    def require_operands(self) -> Or:
        if len(self.operands) < 2:
            raise ValueError("or requires at least two operands")
        return self


class Not(DomainModel):
    kind: Literal["not"] = "not"
    operand: BooleanExpression


class Xor(DomainModel):
    kind: Literal["xor"] = "xor"
    left: BooleanExpression
    right: BooleanExpression


class Implies(DomainModel):
    kind: Literal["implies"] = "implies"
    premise: BooleanExpression
    conclusion: BooleanExpression


class Equivalent(DomainModel):
    kind: Literal["equivalent"] = "equivalent"
    left: BooleanExpression
    right: BooleanExpression


class Cardinality(DomainModel):
    kind: Literal["cardinality"] = "cardinality"
    operands: tuple[BooleanExpression, ...]
    minimum: int
    maximum: int

    @model_validator(mode="after")
    def validate_bounds(self) -> Cardinality:
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("cardinality bounds must satisfy 0 <= minimum <= maximum")
        if self.maximum > len(self.operands):
            raise ValueError("cardinality maximum cannot exceed the operand count")
        return self


class AllDifferent(DomainModel):
    kind: Literal["all_different"] = "all_different"
    operands: tuple[NumericExpression, ...]

    @model_validator(mode="after")
    def require_operands(self) -> AllDifferent:
        if len(self.operands) < 2:
            raise ValueError("all_different requires at least two operands")
        return self


BooleanExpression = Annotated[
    Equal
    | NotEqual
    | LessThan
    | LessThanOrEqual
    | GreaterThan
    | GreaterThanOrEqual
    | And
    | Or
    | Not
    | Xor
    | Implies
    | Equivalent
    | Cardinality
    | AllDifferent,
    Field(discriminator="kind"),
]

Expression = NumericExpression | BooleanExpression

for model in (
    Add,
    Subtract,
    Multiply,
    ExactDivide,
    Modulo,
    Negate,
    And,
    Or,
    Not,
    Xor,
    Implies,
    Equivalent,
    Cardinality,
):
    model.model_rebuild()
