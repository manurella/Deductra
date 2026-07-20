# Logic Grid Structured Input and Export

FAM-LG-006 provides the family-specific structured-document boundary for Logic Grid authoring. It
accepts an in-memory UTF-8 JSON or YAML document, validates it as the existing immutable builder
draft, and returns the same normalized preview and optional readiness proof used by guided
authoring. It does not create a second puzzle model or a second validation path.

## Import pipeline

`import_logic_grid_builder` requires the caller to select `json` or `yaml` explicitly. Content is
never guessed from a filename or document prefix. One import proceeds through these ordered gates:

1. confirm that the source is text or bytes and has a valid UTF-8 representation;
2. enforce the byte limit before invoking a parser;
3. inspect JSON nesting or YAML parser events before constructing a value tree;
4. reject ambiguous or unsupported syntax, duplicate keys, and non-JSON value types;
5. enforce total-node, depth, and per-collection limits before model validation;
6. validate the result against `LogicGridBuilderDraft` using strict JSON semantics; and
7. pass the draft to the canonical builder assessment and optional proof gate.

The public result is `LogicGridStructuredImport`. A rejected result contains structured errors and
no partial draft. An accepted result contains the immutable draft, its builder assessment, and a
plain deterministic normalized preview. Acceptance means that the document satisfies the draft
schema; the nested assessment separately states whether the puzzle is incomplete, invalid,
unproven, warning-bearing, or ready.

## Resource limits

The v1 boundary applies these fixed limits before the recursive Pydantic model is constructed:

| Resource | Limit |
| --- | ---: |
| UTF-8 document size | 262,144 bytes |
| Structured values | 8,192 nodes |
| Collection nesting | 32 levels |
| Fields or items in one collection | 512 |

The builder's smaller family limits still apply afterward: at most eight categories, eight items
per category, 128 clues, and 16 nested predicate levels. The two layers serve different purposes.
Parser limits protect the boundary from resource exhaustion; builder limits keep authored puzzles
within the supported interactive and reasoning envelope.

## YAML profile

YAML input uses a deliberately restricted, JSON-compatible profile:

- exactly one document;
- unique string mapping keys;
- standard null, Boolean, integer, finite floating-point, string, sequence, and mapping values;
- no anchors, aliases, merge references, custom tags, binary values, sets, or language-object tags;
  and
- timestamp-looking scalars remain strings so JSON and YAML follow the same draft semantics.

The adapter subclasses PyYAML's safe loader and then validates the constructed tree independently.
Rejecting aliases, rather than merely limiting their expansion, keeps the canonical input explicit
and avoids parser-dependent reference semantics.

## Corrective errors

Parser and schema failures never escape as raw library exceptions. Every `StructuredInputError`
has a stable code, field path, plain-language problem and reason, corrective action, and optional
one-based line, column, expected value, and received-type description. Received descriptions do
not echo source values, which prevents accidental disclosure through logs or interfaces.

Syntax failures use the root path because the document tree does not yet exist. Schema failures
use paths such as `categories[1].items[0].label`. Family-semantic problems remain the builder's
richer `BuilderValidationMessage` values in the accepted result rather than being flattened into
parse errors.

## Deterministic export

`export_logic_grid_builder_json` emits canonical UTF-8 JSON with normalized Unicode, sorted object
keys, no insignificant whitespace, and one trailing newline. It is the identity-oriented format.

`export_logic_grid_builder_yaml` emits a stable, human-readable document in model field order with
Unicode text, block collections, no aliases, no implementation-specific tags, and one explicit
document start. Importing either export recreates the same immutable draft and normalized preview.

The checked-in `logic-grid-structured-import-v1.schema.json` defines the result contract. The
existing `logic-grid-builder-draft-v1.schema.json` remains the authoritative input model.

## Architecture and exclusions

`families.logic_grid.structured_io` is an outer family application service beside the guided
builder. It may compose the family and builder contracts and may depend on the admitted YAML
adapter. It does not own family semantics and may not import persistence, generation, reporting,
agents, or delivery code.

This packet adds no filesystem reader or writer, filename inference, CLI command, terminal screen,
mutable draft storage, autosave, play workflow, generation, difficulty or novelty evaluation, or
report. Later delivery adapters must apply their own path, overwrite, and file-permission policy
before calling this in-memory boundary.
