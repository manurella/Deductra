# Logic Equations Human Rules

FAM-LE-002 supplies the first concrete family rule catalogue for the common human-reasoning
engine. The rules discover deterministic, explainable proposals; they do not authorize state
changes.

## Catalogue

The version 1 catalogue orders six technique groups:

1. direct equality, inequality, comparison, and domain-bound relations;
2. all-different propagation;
3. arithmetic relations, including offsets, sums, products, and exact division;
4. parity and divisibility expressed through modulo relations;
5. disjunction elimination; and
6. conditional implication.

Arithmetic rules operate only when an expression has exactly one unresolved variable and
every other referenced variable is fixed in the source state. The rule evaluates each current
candidate for that single variable. It proposes an assignment when exactly one candidate
satisfies the constraint, or individual exclusions when multiple candidates remain valid.
If no candidate satisfies the constraint, the rule fails closed and emits no proposal.

All-different propagation cites the existing assignment as a premise and the all-different
constraint as supporting evidence. Every proposal carries a stable rule identity, source-state
hash, affected variable, supporting constraint, information gain, pedagogical rank, and typed
assignment or exclusion conclusion.

## Determinism and search boundary

Candidate identifiers derive from the rule, conclusion, source-state hash, and supporting
constraint. Common discovery sorts applications canonically, so changing catalogue iteration
order does not change the result.

Rules never enumerate combinations for two or more unresolved variables, open branches, or
silently invoke a solver. Repeated single-variable deductions can form a disclosed multi-clue
chain through the common engine. When no rule applies, discovery returns no candidates and
the common engine's existing stalled behavior remains authoritative.

## Verification boundary

Human-rule output is not proof. FAM-LE-003 connects these rules to the existing verified solve
loop through independent Logic Equations encodings. A proposal may change canonical state
only after the common authority boundary receives accepted backend evidence.

This packet adds no parser, search coordinator, solution enumerator, family checker, Golden
puzzle, generator, CLI, interface, or trace exporter.
