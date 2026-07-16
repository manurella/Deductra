# Logic Equations Specification

FAM-LE-001 begins M2 by specializing the common immutable puzzle contract for one
finite-domain arithmetic-assignment family. `LogicEquationsSpec` remains a `PuzzleSpec`;
it adds family invariants without introducing a second canonical model.

## Canonical shape

A version 1 Logic Equations specification has:

- family identifier `logic-equations` and schema version `1.0.0`;
- exactly one ordered domain containing the integer values `1..n`;
- exactly `n` uniquely labelled arithmetic variables over that domain;
- one all-different constraint covering every variable exactly once;
- one or more normalized arithmetic constraints;
- one textual clue for each arithmetic constraint; and
- only assignment or exclusion givens whose references close over the specification.

Arithmetic constraints use the common expression tree. Version 1 admits integer constants,
variable references, addition, subtraction, multiplication, exact division, modulo, negation,
comparisons, conjunction, disjunction, negation, and implication. Expression variable
references are validated against the declared variables. A literal zero divisor is rejected.

The family exposes a stable JSON Schema identity and a deterministically generated checked-in
schema. Runtime validation remains authoritative for cross-field invariants such as `1..n`,
all-different coverage, and reference closure because those constraints are not completely
expressible in portable JSON Schema.

## Boundary

This packet defines data and validation only. It does not parse user syntax, select or apply
human rules, encode a solver backend, prove a solution, generate a puzzle, provide Golden
content, export a solve trace, or expose a CLI or user interface. Those capabilities require
later reviewed packets and must consume this specification through the common platform.
