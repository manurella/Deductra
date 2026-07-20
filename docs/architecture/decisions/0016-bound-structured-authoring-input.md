# ADR-0016: Bound structured authoring input before model validation

## Status

Accepted

## Context

Logic Grid power users need JSON and YAML authoring that produces the same normalized draft,
preview, and proof behavior as guided input. General-purpose parsers accept constructs that are
ambiguous across implementations or unsafe for a canonical product contract, including duplicate
keys, YAML aliases, custom tags, multiple documents, and deeply recursive values. Pydantic model
validation happens after parsing and therefore cannot by itself prevent parser resource
exhaustion.

JSON and YAML must not acquire different family semantics. Parser exceptions and raw source values
must also remain outside future CLI and terminal presentation surfaces.

## Decision

Add `families.logic_grid.structured_io` as an outer family application service. Require an explicit
format and apply UTF-8 byte, node, depth, and per-collection limits before constructing the
recursive builder model. Reject duplicate keys, non-string object keys, multiple YAML documents,
anchors, aliases, merges, custom tags, and non-JSON value types.

Admit PyYAML 6.0.3 directly and use a restricted `SafeLoader` subclass for the YAML adapter. Treat
timestamp-looking YAML scalars as strings, then serialize the parsed tree to canonical JSON before
strict `LogicGridBuilderDraft` validation. This gives JSON and YAML the same Pydantic input
semantics.

Return a versioned immutable result with sanitized corrective errors, the canonical builder
assessment, and a deterministic normalized preview. Publish its v1 JSON Schema. Export identity-
oriented canonical JSON and human-readable deterministic YAML from the same draft model.

Keep filesystem and delivery policy outside this module. The adapter accepts and returns in-memory
values only.

## Consequences

- JSON and YAML round-trip to one immutable authoring contract and one family-semantic assessment.
- Hostile or accidental parser expansion is bounded before recursive model construction.
- Duplicate or implementation-specific YAML meaning is rejected rather than normalized silently.
- Presentation layers receive stable corrective information without raw parser exceptions or
  echoed source values.
- PyYAML becomes a governed direct runtime dependency with an exact lock and dedicated security
  tests.
- The supported YAML profile is intentionally smaller than the full YAML language.
- Future file and terminal adapters must still implement path safety, overwrite policy, permissions,
  and user interaction; this decision does not authorize those delivery concerns.
