# ADR-0015: Keep guided authoring presentation-neutral

## Status

Accepted

## Context

Logic Grid needs beginner-friendly construction, live semantic validation, normalized preview, and
proof evidence. Implementing those rules directly inside a future terminal screen would couple
family semantics to one interface, make structured import behave differently, and make detailed
validation difficult to test without a UI.

The inner Logic Grid specification and human-rule modules must remain independent of proof backends
and delivery code. At the same time, a complete authoring assessment must be able to compose those
inner contracts with independent verification.

## Decision

Represent guided input as a versioned immutable `LogicGridBuilderDraft` with family-owned clue
templates. Expose a presentation-neutral assessment service that returns staged status, actionable
field-path messages, normalized previews, a canonical `LogicGridSpec`, and optional proof evidence.

Treat `families.logic_grid.builder` as an outer family application service. It may depend on domain,
family, reasoning, and verification contracts. Specification, schema, rules, and solver modules keep
their existing inward dependency restrictions. Delivery, persistence, generation, reports, and
agents remain outside the builder.

Publish the draft as a checked-in v1 JSON Schema. Structured parsers and terminal screens will
consume the contract later; they do not define its semantics.

## Consequences

- CLI, terminal, and structured-input adapters can share one validation and compilation path.
- Incomplete drafts can be represented without weakening the complete puzzle specification.
- Validation remains plain-language, field-scoped, deterministic, and testable without a UI.
- Proof status cannot be fabricated by presentation code, and hidden search cannot silently enter
  the beginner workflow.
- The builder imports solver authority and therefore is not an inner family module; architecture
  tests must preserve this explicit distinction.
- The recursive draft schema requires future file-import adapters to add byte, nesting, and parsing
  limits before model validation.
