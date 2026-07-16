# Logic Equations Backend Encodings

FAM-LE-003 extends the independent proof boundary to the normalized Logic Equations
expression catalogue. Human-rule proposals may now reach canonical reduction only after Z3
and CP-SAT independently establish that the negated conclusion is unsatisfiable.

## Numeric semantics

Solver variables retain the common finite-domain integer codes used by CR-004. Logic
Equations expressions, however, operate on each `DomainValue.numeric_value`. Both encoders
translate codes to those declared integers explicitly. They reject non-integer arithmetic
domains instead of assuming a relationship between a value identifier, ordinal, code, and
numeric meaning.

The supported expression surface is:

- integer constants and variable references;
- addition, subtraction, multiplication, negation, exact division, and modulo;
- equality, inequality, and ordered comparisons;
- conjunction, disjunction, negation, and implication.

Exact division is valid only for a nonzero divisor and an integral result. Modulo requires a
positive divisor. Invalid arithmetic makes its containing comparison false in both encoders.

## Independent implementations

The Z3 backend constructs symbolic integer and Boolean formulas. Exact-division and modulo
validity conditions are included in the asserted formula, and clue constraints retain tracked
references for unsatisfiable-core evidence.

The CP-SAT backend independently evaluates the typed expression over the current candidate
codes and adds an allowed-assignment table. It does not import or reuse the Z3 translator or
the human-rule evaluator. Table construction is capped at 1,000,000 candidate combinations;
larger relations fail closed as invalid encodings rather than consuming unbounded memory.

Both backends advertise encoding version `finite-domain-arithmetic-v1`. Active constraint
kinds outside domain, all-different, and arithmetic remain unsupported and fail closed.
Each backend independently checks that the source puzzle, state, and disclosed assumptions
are satisfiable before adding the negated claim. An already inconsistent source is an invalid
proof context and cannot authorize arbitrary conclusions through logical explosion.

## Authority and remaining boundary

Differential tests require both backends to agree on valid assignments and eliminations
across the expression catalogue. Satisfiable counterexamples reject deductions, invalid
encodings reject deductions, timeouts remain inconclusive, and backend disagreement remains
quarantined.

This packet enables verified human-rule reduction for Logic Equations. It does not add a
family parser, final-solution checker, two-solution uniqueness enumeration, Golden puzzle,
generator, CLI, interface, or trace export.
