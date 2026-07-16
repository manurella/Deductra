# Logic Equations CLI and Trace Delivery

Last reviewed: 2026-07-16

FAM-LE-005 completes the first deterministic family kernel with a narrow command-line
adapter. The supported command is:

```shell
deductra solve four-sigils
```

The equivalent module invocation is `python -m deductra solve four-sigils`. The command
solves the fixed Golden Easy puzzle through the common human-reasoning engine. Every state
change requires agreement from the independent Z3 and CP-SAT backends. The CLI does not
contain puzzle-solving rules or bypass the verification authority boundary.

## Trace export

Passing `--trace PATH` creates a UTF-8 JSON representation of the existing
`HumanSolveTrace` v1 contract. Keys and indentation are stable, the fixed Golden inputs
produce byte-identical output, and the serialized trace validates through the canonical
domain model. Export refuses to overwrite an existing path.

The trace records disclosed rule attempts, proof-certificate references, canonical events,
source and result state hashes, and the final trace hash. It does not include backend debug
artifacts, raw solver output, local paths, environment data, or hidden search.

## Boundary

The CLI is an outer delivery adapter. It may compose family, reasoning, and verification
capabilities, while those inner packages remain independent of command-line concerns. This
packet introduces no parser syntax for user-authored puzzles, interactive terminal UI,
generator, persistence workflow, report rendering, network service, or stable public API.
