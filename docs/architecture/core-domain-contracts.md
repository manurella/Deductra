# Core Domain Contracts

Last reviewed: 2026-07-15

CR-001 establishes the first M1 product boundary: a family-neutral, immutable representation of a puzzle. It defines data contracts only. It does not solve, generate, render, persist, or explain puzzles.

## Contract surface

The `deductra.domain` package owns:

- validated identifiers;
- deterministic canonical JSON and SHA-256 hashing;
- domains, values, and variables;
- discriminated atoms, expression trees, and common constraints;
- clue, display, lineage, and provenance records required by `PuzzleSpec`;
- the versioned `PuzzleSpec` JSON Schema.

Every model rejects unknown fields, uses strict validation, and is frozen after construction. Nested metadata containers are converted to immutable mappings and tuples. A puzzle revision must use unique identifiers and may only reference domains, variables, constraints, and clues present in that same specification.

## Authority and safety

Clue text is presentation and provenance data; constraints are the machine-readable authority. Expressions are typed trees. Executable strings, callbacks, and dynamic evaluation are not accepted puzzle data.

Canonical JSON uses UTF-8, normalized Unicode, sorted keys, no insignificant whitespace, and rejects non-finite numbers. Its SHA-256 digest is deterministic integrity evidence, not encryption or a digital signature.

## Schema lifecycle

The public schema is `schemas/puzzle-spec-v1.schema.json`. It is generated from `PuzzleSpec` by `scripts/export_json_schema.py`, and tests fail when the checked-in schema drifts from the model. Breaking serialized-contract changes require a new schema version, migration or adapter policy, and an architecture decision.

## Explicit exclusions

CR-001 contains no puzzle-family adapter, solver backend, state reducer, event store, generator, UI, report renderer, memory system, or agent runtime. Those capabilities require later packets.
