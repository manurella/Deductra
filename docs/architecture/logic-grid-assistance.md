# Logic Grid Assistance

FAM-LG-010 provides clue-aware move evaluation and progressive hints without weakening the
presentation-neutral play reducer. Assistance is a separate application service: play actions remain
tentative until this service independently proves or refutes their exact logical atom.

## Move evaluation

Evaluation starts from the immutable puzzle and identifies one accepted assignment or exclusion
event in the supplied replay-verified session. The claimed atom is checked against the complete
puzzle constraints by both independent Logic Grid verification backends. If it is not entailed, the
service checks the exact opposite atom. Only a cross-verified result may be reported as `supported`
or `contradicted`; disagreement, invalid evidence, resource limits, and unknown outcomes fail closed
as `quarantined` or `inconclusive`.

Each evaluation binds the attempt, play event, session state, puzzle revision, atom, backend
certificates, and a stable semantic evidence fingerprint. Runtime measurements are retained for
audit but excluded from stable identities.

## Evidence-backed hints

Hints run the deterministic Logic Grid human-rule catalogue over a reasoning state built only from
fixed puzzle facts and individually cross-verified active marks. A contradicted active mark blocks
new deductions and returns corrective evaluation evidence. Human-rule exhaustion is explicit and
does not fall back to hidden search.

One verified technique record contains the source-state hash, rule identity, exact premises,
supporting clue identifiers and constraints, conclusion, and independent certificates. A separate
disclosure view reveals that record progressively:

1. reflection without a target;
2. area and clue attention;
3. technique name;
4. exact premises;
5. a deduction prompt without the conclusion;
6. the verified conclusion and explanation; and
7. an explicit suggested play action.

All levels reference the same verified evidence. The highest level proposes an action but does not
apply it; a delivery adapter must submit that action through the ordinary play service. Exam mode
withholds assistance before completion.

## Public contract

`LogicGridAssistanceContractDocument` is immutable and versioned as `1.0.0`. It contains exactly one
move-evaluation or hint-result payload. The checked-in major-version schema is
`schemas/logic-grid-assistance-v1.schema.json`. Content hashes protect the semantic evidence and
presentation result independently, so disclosure can be tested without making hidden audit fields
part of user-facing text.

## Deliberate exclusions

This packet does not itself mutate play sessions, persist assistance records, normalize memory
events, infer mastery, choose puzzles, generate content, render interfaces, compose reports, or
continue play automatically. FAM-LG-011 later added a separate attempt-persistence integration that
durably retains a sealed `LogicGridMoveEvaluation` and normalizes only its decided outcome into
common memory; see [Logic Grid attempt persistence](logic-grid-attempt-persistence.md) and
[ADR-0021](decisions/0021-persist-verified-move-evaluations-into-attempt-memory.md). That
integration depends only on the sealed evaluation type this module exports, not on the service, its
reasoning composition, or its verification backends; it never re-verifies a stored evaluation, and it
does not yet cover hint evidence. Any further integration must consume the same typed evidence
boundary and preserve its fail-closed authority rules.
