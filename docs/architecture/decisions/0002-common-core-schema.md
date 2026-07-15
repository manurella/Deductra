# ADR-0002: Establish an immutable common-core schema

- Status: Accepted
- Date: 2026-07-15
- Owner: [@manurella](https://github.com/manurella)

## Context

M1 needs one family-neutral boundary before reasoning, verification, persistence, or puzzle-specific behavior can be implemented. Plain dictionaries would allow ambiguous variants, silent extra fields, mutable specifications, and serialization drift. The same contract must work on Python 3.13 and 3.14 and emit a reviewable JSON Schema.

## Decision

Create `deductra.domain` inside the existing single distribution package. Use strict frozen Pydantic 2.x models, discriminated unions for variant data, explicit reference validation, and deterministic canonical JSON. Admit `pydantic>=2.13,<3` as the first runtime dependency. Check the generated PuzzleSpec v1 schema into `schemas` and verify it against the model in tests.

## Dependency admission

- Purpose: runtime validation, immutable typed models, discriminated unions, and JSON Schema generation.
- Standard-library gap: the standard library does not provide this integrated validation and schema surface.
- Maintenance and compatibility: Pydantic is actively maintained, MIT licensed, and publishes Python 3.13 and 3.14 support.
- Cost: Pydantic Core and small typing support packages become transitive runtime dependencies.
- Alternatives: hand-written dataclasses and validators would increase custom validation and schema-generation code; attrs does not provide the required schema boundary by itself.
- Removal strategy: the public JSON Schema and domain tests define the migration target if the implementation library changes.
- Owner: [@manurella](https://github.com/manurella).

## Consequences

The package now has one declared runtime dependency and a serialized contract that requires version discipline. Product code may build inward toward `deductra.domain`; the domain package may not import delivery, persistence, solver, reporting, UI, or agent layers. Later packets must extend this boundary deliberately rather than creating parallel domain models.
