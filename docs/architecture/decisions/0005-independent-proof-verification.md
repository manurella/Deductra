# ADR-0005: Verify deductions through independent solver encodings

- Status: Accepted
- Date: 2026-07-16
- Owner: [@manurella](https://github.com/manurella)

## Context

Deductra must distinguish a plausible deduction from one entailed by the current puzzle state. A single solver integration can contain modeling defects, and timeout or indeterminate results do not establish entailment.

## Decision

Represent every supported deduction as a source-bound proof obligation whose negation is checked for unsatisfiability. Use Z3 as the tracked logical proof backend and OR-Tools CP-SAT as an independently constructed finite-domain verifier. Treat unknown and timeout outcomes as inconclusive, and quarantine any satisfiable/unsatisfiable disagreement. Only an accepted coordinator decision may authorize the existing pure reducer.

The first encoding is intentionally restricted to assignment and elimination claims over domain and all-different constraints. Unsupported semantics fail closed.

## Alternatives considered

- Trust one solver result. Rejected because one encoding defect could silently authorize an invalid deduction.
- Compare two solvers fed by one generated model. Rejected because shared translation defects would defeat independence.
- Accept a timeout as probable validity. Rejected because absence of a counterexample within a time budget is not proof.

## Consequences

The runtime gains two native solver dependencies and their transitive footprint. Every supported constraint requires two semantic implementations and agreement tests. In return, verification outcomes have explicit evidence, indeterminate states cannot mutate canonical projections, and cross-backend disagreement becomes visible rather than silently resolved.

## Reconsideration triggers

Revisit this decision if a backend loses supported-platform wheels, a material security or licensing concern appears, independent encodings cannot be maintained, or a proof-producing backend offers stronger independently checkable evidence.
