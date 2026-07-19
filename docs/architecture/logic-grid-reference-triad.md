# Logic Grid Reference Triad

FAM-LG-004 establishes three fixed Logic Grid reference puzzles and an independent final-solution
checker. The references are original project content and provide deterministic acceptance fixtures
for later interaction, learning, replay, generation, and reporting packets.

## Reference set

| Reference | Structural size | Calibration role | Categories | Presentation clues |
| --- | ---: | --- | ---: | ---: |
| Harbor Morning | 3x3 | Easy | 3 | 4 |
| Gallery Opening | 4x4 | Medium | 4 | 9 |
| Observatory Rotation | 5x5 | Hard | 5 | 16 |

Every category is a bijection over the canonical anchor rows. Each presentation clue fixes one
association, and the final item in each non-anchor category follows from bijection. Removing any
one presentation clue admits a concrete alternative solution, so no clue is redundant for
uniqueness.

The Easy, Medium, and Hard labels are stable structural calibration anchors. They describe the
increasing dimensions, category count, and deduction volume of this first reference triad. Later
difficulty work must measure trace features and may enrich calibration evidence without silently
changing these versioned fixtures.

## Independent final checking

`check_logic_grid_solution` accepts only a complete sequence of assignments. It validates unknown,
duplicate, and missing variables; anchor-row membership; declared givens; category bijections; and
every normalized clue expression. It evaluates the Logic Grid contract directly and does not call
the human-rule evaluator, Z3 translator, or CP-SAT translator.

Row identity, ordinal order, and exact numeric values remain distinct in the checker. Integer and
rational values are evaluated exactly. Unsupported or incomplete numeric semantics fail instead of
being approximated.

## Uniqueness evidence

The independent checker accepts each canonical solution and rejects altered assignments. Z3 and
CP-SAT separately prove that the source is satisfiable and that negating each non-given canonical
assignment is unsatisfiable. Because the anchor assignments are fixed givens and every remaining
assignment is entailed, the accepted solution is unique.

The common verified human-reasoning loop also solves every reference deterministically. Its
deductions remain subject to cross-verification; the fixed solution constants are test or consumer
expectations and never authorize state changes.

## Packet boundary

This packet adds reference data, final checking, and acceptance evidence only. It does not add a
parser, general search interface, CLI command, guided builder, playable workflow, generator,
difficulty engine, persistence behavior, report composition, or user interface.
