# Logic Grid Guided Builder

FAM-LG-005 introduces a family-specific authoring service for constructing normalized Logic Grid
puzzles without requiring a user to write formal JSON. It is a presentation-neutral application
boundary: later CLI and terminal screens can render its stages, messages, templates, and previews
without reimplementing family semantics.

## Staged contract

`LogicGridBuilderDraft` is immutable and deliberately permits incomplete authoring state. An
assessment places a draft at one of six stages:

1. profile;
2. categories;
3. clues;
4. preview;
5. proof; or
6. ready.

The aggregate status is `incomplete`, `invalid`, `unproven`, `warning`, or `valid`. Every message
identifies a field path, states the problem and reason in plain language, and gives a corrective
action. Presentation adapters should display those fields together and must not reduce them to a
generic parse failure.

The beginner-facing model uses stable category and item keys, visible labels, equal-sized category
tables, one selected anchor category, and guided clue templates. Advanced identifiers, constraint
objects, and solver encodings are derived rather than entered manually.

## Guided clue catalogue

The v1 builder composes the complete normalized Logic Grid expression surface from user-facing item
references:

- same-row and different-row association;
- strict ordering;
- exact numeric difference;
- conjunction and inclusive alternatives;
- negation and exclusive alternatives;
- implication and equivalence; and
- bounded cardinality.

Templates may be nested to express compound clues. Nesting, category count, item count, clue count,
key shape, and visible text length are bounded before compilation. References must resolve to the
current category tables. Numeric templates require complete, unique exact values on the anchor
category, and misleading numeric values on non-anchor categories are rejected.

## Normalized preview and compilation

A structurally complete draft compiles to the existing immutable `LogicGridSpec`; there is no
parallel puzzle model. Canonical identifiers derive from the safe draft, category, item, and clue
keys. Generated presentation text remains separate from the formal expression, while every clue
retains exact constraint provenance.

The preview includes category tables, association-grid rows, generated or authored clue text,
formal variable and constraint counts, and the canonical puzzle fingerprint. The checked-in
`logic-grid-builder-draft-v1.schema.json` describes the immutable draft contract for future
structured-input adapters.

## Proof gate

Structural compilation returns `unproven` until proof is requested. The proof gate runs the common
human-reasoning engine with the Logic Grid rule catalogue and independent Z3 and CP-SAT authority.
If disclosed rules reach a complete state, every applied reduction has dual-backend evidence. The
resulting assignments are replayed and checked by the independent final checker. Together, the
entailed candidate reductions and fixed anchor givens establish one unique solution.

If the human rule catalogue stalls, reaches a limit, or receives inconclusive authority, the draft
remains `unproven`. The builder does not silently invoke general search and does not misclassify a
hard, underconstrained, or inconsistent draft as valid.

## Dependency and packet boundaries

The builder is an outer family application service. It may compose family contracts, reasoning,
and verification, but it does not belong to the inner specification or human-rule layers. It may
not import delivery adapters, persistence, reports, generation, or agents.

This packet adds no file parser, YAML dependency, terminal screen, mutable draft store, save action,
play workflow, general search, difficulty score, novelty analysis, generation, or report. Those
capabilities must consume this contract in later bounded packets.
