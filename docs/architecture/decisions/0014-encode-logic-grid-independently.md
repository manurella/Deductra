# ADR-0014: Encode Logic Grid independently in Z3 and CP-SAT

## Status

Accepted

## Date

2026-07-19

## Owner

Repository owner

## Context

FAM-LG-002 can propose deterministic Logic Grid deductions, but those proposals have no
authority until independent backends prove them. Logic Grid expressions combine three
different meanings: anchor-row identity for association, anchor ordinal for before-and-after
relations, and declared exact numeric values for constants and differences. Collapsing those
meanings into one implicit integer representation would make valid-looking proofs unsound.

The common verification package must remain inward-facing and cannot import a concrete family
package. The two proof backends must also retain genuinely different translation paths so one
shared expression defect cannot establish false agreement.

## Decision

Carry the stable family identifier as inert data in the prepared finite-domain problem. The
common Z3 and CP-SAT adapters select reviewed Logic Grid translators by that identifier without
importing family implementation modules.

Encode direct item equality and inequality over stable anchor-row codes. Encode direct ordered
comparisons over those codes, whose order is guaranteed by the Logic Grid anchor contract.
Encode constants and subtraction through declared exact numeric values, preserving rational
values without floating-point conversion.

Construct native symbolic Boolean and arithmetic formulas in Z3. Independently evaluate the
typed clue over candidate-code combinations for CP-SAT and add an allowed-assignment table.
Support conjunction, disjunction, negation, exclusive alternatives, implication, equivalence,
and bounded cardinality in both translators.

Cap each CP-SAT Logic Grid table at 1,000,000 candidate combinations and fail closed above that
limit. Require each backend to establish source satisfiability before checking a negated claim.
Identify the family proof contract as `finite-domain-logic-grid-v1` in certificates.

## Alternatives

- Reuse the human-rule evaluator as proof code. Rejected because rule and proof defects would
  no longer be independent.
- Generate both backend models from one intermediate formula. Rejected because a shared
  translation defect would undermine cross-verification.
- Treat row code, ordinal, and numeric value as interchangeable. Rejected because they are
  distinct public contracts even when a fixture happens to align them.
- Convert rational values to floating point. Rejected because proof semantics must remain exact.
- Build unbounded CP-SAT tables. Rejected because a high-arity clue could exhaust memory before
  the solver timeout applies.

## Consequences

Every normalized Logic Grid clue form can now participate in independent proof verification.
Verified human-rule proposals can reach the common reducer only after both backends establish
that the negated conclusion is unsatisfiable. Counterexamples, inconsistent sources, encoding
limits, timeouts, and backend disagreement remain fail-closed.

The CP-SAT table implementation is exact and reviewable but intentionally bounded. High-arity
clues beyond the limit require decomposition or a later independently reviewed native CP-SAT
translator. The family identifier is now part of prepared verification data, but concrete family
packages remain outside the verification dependency boundary.

## Reconsideration triggers

Revisit this decision when accepted Logic Grid content approaches the table limit, when measured
encoding time becomes material, or when a native CP-SAT translator can preserve independent
semantics with a smaller and equally reviewable failure surface.
