# Logic Grid Specification

FAM-LG-001 begins M3 by specializing the common immutable puzzle contract for unordered one-to-one category associations. `LogicGridSpec` remains a `PuzzleSpec`; it adds only the category alignment and anchor semantics required to make association rows canonical.

## Canonical shape

A version 1 Logic Grid specification has:

- family identifier `logic-grid` and schema version `1.0.0`;
- at least three uniquely identified and labelled categories;
- one common domain per category and the same number of items in every domain;
- one aligned entity-assignment variable for every item;
- one declared anchor category whose domain is the assignment range for every variable;
- structural givens that map anchor items to their corresponding anchor values;
- exactly one all-different constraint for each category;
- one or more normalized arithmetic-expression constraints for clues; and
- complete clue coverage with primary provenance for every clue constraint.

Category domains preserve item identifiers, labels, ordering, and optional numeric values. A category descriptor aligns those values with item variables in canonical tuple order. Item labels must agree across both representations, category variables partition the complete variable set, and all item and category identities are unique.

## Relationship semantics

Every item variable identifies the anchor row occupied by that item. Two item variables are associated when their values are equal and excluded when their values differ. Category all-different constraints make each category a bijection over the anchor rows.

The safe common expression tree represents alternatives, exclusive alternatives, cardinality, implication, equivalence, ordering, numeric differences, and compound clues. All references must close over declared item variables. Ordered comparisons require an ordered anchor domain. Constants and subtraction require complete numeric values on the anchor domain. Executable expressions, backend codes, and untyped callbacks are not accepted puzzle data.

Clues may compile into multiple normalized constraints, and a constraint may be supported by multiple clues. Each constraint still identifies one primary source clue, which must reference that constraint. Structural all-different constraints are not presentation clues.

## Validation boundary

Runtime validation enforces category size, identity, variable partitioning, label alignment, anchor mapping, bijection coverage, expression semantics, given consistency, and clue provenance. The family also exposes a stable JSON Schema identity and a deterministically generated checked-in schema. JSON Schema provides the external structural contract; runtime validation remains authoritative for cross-field invariants.

## Packet boundary

This packet defines immutable data and validation only. It does not parse user syntax, discover or apply human rules, encode Z3 or CP-SAT, enumerate solutions, provide Golden content, generate puzzles, render a grid, compose reports, or expose a CLI or interactive interface. Those capabilities require later M3 packets and must consume this specification without bypassing common verification authority.
