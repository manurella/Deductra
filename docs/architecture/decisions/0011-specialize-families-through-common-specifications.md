# ADR-0011: Specialize families through the common puzzle specification

## Status

Accepted

## Date

2026-07-16

## Owner

Repository owner

## Context

M2 needs a concrete Logic Equations schema while preserving the family-neutral contracts
established during M1. A parallel family model would create competing serialization,
identity, provenance, and clue representations. Using an unrestricted `PuzzleSpec` directly
would leave important family invariants implicit and defer malformed inputs to solver code.

## Decision

Represent Logic Equations as an immutable `LogicEquationsSpec` specialization of
`PuzzleSpec`. Enforce its permutation-domain, variable, all-different, arithmetic-expression,
clue-coverage, and reference-closure invariants at validation time.

Place family code under `deductra.families.logic_equations`. The family boundary may depend
on the common domain contract; the common domain and other inward packages may not depend
on a family. Keep parser, reasoning rules, backend encodings, content, delivery, and
generation outside this packet.

## Alternatives

- Add family-specific fields to `PuzzleSpec`. Rejected because they would leak one family's
  concerns into every other family.
- Create a separate unrelated schema and translate later. Rejected because two canonical
  models would invite identity and serialization drift.
- Validate only when solving. Rejected because invalid puzzle data should fail before it
  reaches reasoning or backend integrations.

## Consequences

The first family proves that concrete specifications can reuse the common substrate without
special-case bypasses. Cross-field validation is available before parser and solver work.
The family package adds no dependency and no new deployment boundary.

The `1..n` domain and normalized expression catalogue are versioned compatibility choices.
A future incompatible family shape requires a new schema version and decision record.

## Reconsideration triggers

Revisit this decision if a second family cannot specialize `PuzzleSpec` without weakening
its invariants, or if a required Logic Equations construct cannot be represented by the
common expression tree.

