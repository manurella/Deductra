# Logic Grid Human Rules

FAM-LG-002 supplies deterministic Logic Grid techniques for the common human-reasoning
engine. Each application proposes one typed assignment or exclusion with stable identity,
source-state binding, supporting constraints, and explicit premises. A proposal cannot mutate
canonical state and is not proof.

## Catalogue

The version 1 catalogue orders five technique groups:

1. direct association, including matches and exclusions;
2. category bijection, including occupied-row elimination and sole-position assignment;
3. ordered association through disclosed minimum and maximum bounds;
4. numeric relations, including exact differences; and
5. compound logic expressed through conjunction, alternatives, exclusive alternatives,
   implication, equivalence, negation, and cardinality.

Direct equality intersects the current candidate rows for two items. A fixed item can therefore
assign its match, while candidates absent from the other item can be excluded. Direct inequality
uses a fixed association to exclude the same row from the other item.

Category bijection eliminates a row already occupied by another item in the same category. It
can also assign a row that remains available to only one category item, but only when existing
assignment or exclusion atoms disclose why every other item cannot occupy that row.

## Local completion boundary

Ordering between two unresolved item variables uses only current candidate minima and maxima.
Other ordered, numeric, and compound clues are evaluated only when exactly one referenced
variable remains unresolved. Every other referenced variable must be fixed and is cited as an
assignment premise. The rule tests only the unresolved variable's current domain, then proposes
the sole valid assignment or individual exclusions for invalid candidates.

Rules do not enumerate assignments for two or more unresolved variables, open branches, invoke
a backend, or silently search. A locally contradictory clue emits no deduction; contradiction
authority remains outside the family rule catalogue.

## Determinism and authority

Candidate identity derives from the rule, conclusion, source-state hash, and supporting
constraint. Common discovery provides canonical ordering independent of catalogue iteration.
The catalogue is family-scoped and returns no applications for another puzzle family.

Independent Logic Grid verification is a later M3 packet. Until that boundary exists, these
rules are inspectable proposal semantics only; they are not connected to verified state
reduction. This packet adds no backend encoding, search coordinator, solution checker, Golden
puzzle, parser, generator, interface, report composition, or product behavior.
