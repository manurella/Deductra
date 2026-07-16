# ADR-0012: Encode Logic Equations independently in Z3 and CP-SAT

## Status

Accepted

## Date

2026-07-16

## Owner

Repository owner

## Context

FAM-LE-002 can propose explainable arithmetic deductions, but human rules are not proof.
CR-004's backends intentionally supported only domain and all-different constraints. Logic
Equations requires arithmetic and propositional semantics without weakening the existing
independent-verification rule.

Internal solver variables use stable domain codes while puzzle expressions use declared
numeric values. Treating those representations as identical would silently misencode
otherwise valid puzzles.

## Decision

Translate domain codes to declared integer values explicitly in both backends. Build a native
symbolic expression in Z3 and an independently evaluated allowed-assignment table in CP-SAT.
Do not share solver expressions or expression-evaluation code between the two backends.

Cap a CP-SAT arithmetic table at 1,000,000 candidate combinations and fail closed above the
limit. Continue rejecting every active constraint kind without two reviewed encodings.
Version the expanded backend contract as `finite-domain-arithmetic-v1`.

Require each backend to establish source satisfiability before checking the negated claim.
Treat an already unsatisfiable source as an invalid proof context rather than proof of the
proposed conclusion.

## Alternatives

- Generate both solver models from one intermediate formula. Rejected because a shared
  translation defect would undermine differential verification.
- Assume numeric value equals internal code or ordinal. Rejected because those are distinct
  contracts.
- Build unbounded CP-SAT tables. Rejected because a crafted high-arity expression could
  exhaust memory before a solver timeout applies.
- Treat one backend as sufficient for arithmetic. Rejected because Logic Equations is the
  reference kernel intended to validate cross-backend proof behavior.

## Consequences

Supported Logic Equations deductions can be cross-verified and reduced through the common
human engine. Differential tests cover the public expression catalogue. Z3 and CP-SAT retain
independent failure modes and artifacts.

The CP-SAT table strategy is exact but intentionally bounded. A valid high-arity relation can
be rejected as an invalid encoding even when Z3 can represent it. Such a case cannot mutate
state and must be simplified, decomposed, or supported by a later reviewed native CP-SAT
translator.

## Reconsideration triggers

Revisit the CP-SAT strategy when accepted reference content approaches the table limit, when
performance evidence shows material encoding cost, or when a native translator can preserve
the same semantic coverage with simpler reviewable bounds.
