# Logic Grid Backend Encodings

FAM-LG-003 connects normalized Logic Grid clues to Deductra's independent proof boundary. A
human-rule proposal can authorize canonical state reduction only when Z3 and CP-SAT independently
show that its negated conclusion is unsatisfiable in the exact source state.

## Three explicit value meanings

Logic Grid encoding keeps three concepts separate:

- an anchor-row code identifies which items are associated;
- the ordered anchor tuple defines ordinal before-and-after relationships; and
- `numeric_value` supplies exact numeric semantics for constants and subtraction.

Direct equality and inequality compare row codes. Direct ordered comparisons compare those codes,
which follow the anchor's validated ordinal order. Expressions containing constants or subtraction
translate through complete declared numeric values. Integer and rational values remain exact;
neither backend uses floating-point arithmetic.

The supported Boolean surface includes equality, inequality, ordered comparisons, conjunction,
disjunction, negation, exclusive alternatives, implication, equivalence, and bounded cardinality.
Numeric expressions include variable references, exact constants, and subtraction. The existing
Logic Grid specification remains authoritative for deciding which combinations are valid puzzle
data.

## Independent translations

The Z3 translator constructs native symbolic formulas. Row identity and order use integer code
variables, while numeric expressions use exact symbolic values selected by those codes.

The CP-SAT translator independently evaluates a clue across current candidate-code combinations
and adds an allowed-assignment table. It does not import the Z3 translator or human-rule evaluator.
Table construction is capped at 1,000,000 combinations. Larger relations produce an invalid
certificate and cannot authorize a state change.

Shared verification preparation validates puzzle, state, obligation, candidate, atom, and active
constraint consistency. It carries the stable family identifier as data so the common backend
adapters can select reviewed translators without importing concrete family packages. Certificates
for this contract use encoding version `finite-domain-logic-grid-v1`.

## Authority and failure behavior

Both backends first prove that the source puzzle, candidate state, and disclosed assumptions are
satisfiable. An inconsistent source is rejected rather than being allowed to prove arbitrary
claims through logical explosion. A satisfiable negated claim rejects the deduction; an encoding
error rejects it; an unknown result is inconclusive; and conflicting backend results are
quarantined.

Differential tests cover direct association, exclusion, ordering without numeric values, exact
rational differences, every accepted compound operator, counterexamples, inconsistent sources,
the CP-SAT resource limit, and verified human-rule reduction.

This packet adds no final-solution checker, uniqueness enumeration, Golden puzzle, parser, search
coordinator, generator, interface, report composition, or product content.
