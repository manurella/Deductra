# Generator Foundation

Last reviewed: 2026-07-16

CR-007 establishes immutable, family-neutral contracts for future verified puzzle generation. It does not generate puzzles. Concrete construction recipes, family adapters, solver coordination, difficulty algorithms, novelty indexes, presentation validation, and persistence remain outside this packet.

## Contract boundary

A `GenerationRequest` names the family, target difficulty, mode, explicit seed, generator version, optional recipe, rule policy, size and style profiles, novelty policy, and resource budgets. Required and forbidden rules cannot overlap. Canonical serialization sorts rule identifiers so the same request has the same representation regardless of runtime hash ordering.

A terminal `GenerationResult` identifies one candidate and carries its complete lineage. Only an accepted result may expose a playable `PuzzleSpec`. Rejected and quarantined candidates retain structured diagnostics without entering normal play.

The future family generator remains responsible for constructing candidates. CR-007 provides ports for independently supplied:

- uniqueness evidence;
- human-trace-based difficulty evidence;
- stable puzzle fingerprints;
- conservative novelty evidence.

These ports contain no solver or family implementation. The generation package depends only on domain and reasoning contracts and does not import verification backends, persistence, graph projection, user-interface, report, or agent packages.

## Lineage and replay

Every generation attempt has an ordered event stream beginning with `generation_requested`. The event vocabulary covers recipe and seed selection, construction and repair, verification requests and outcomes, difficulty, canonicalization, novelty, presentation, and terminal acceptance, rejection, or quarantine.

Events form a zero-based SHA-256 chain. Candidate records link to their assembly event, recipe version, seed, optional parent, mutation operator, and immutable operation parameters. The lineage also records the generator, random-number provider, and dependency versions. The final `PuzzleSpec` remains authoritative even if a future dependency changes seed replay.

## Hard-gate decision

The CR-007 gate evaluates supplied evidence in dependency order:

1. candidate, request, lineage, and family identity;
2. uniqueness;
3. verified human completion;
4. requested difficulty and rule policy;
5. complete fingerprints;
6. novelty.

Zero, multiple, or invalid models are rejected. A stalled human solve, difficulty mismatch, required-rule omission, forbidden-rule use, or known duplicate is rejected. Unknown uniqueness, backend disagreement, inconclusive human solving or novelty, and incomplete evidence are quarantined.

Quarantine has precedence over rejection because uncertainty must remain visible and must never be simplified into a normal content-quality rejection. No quality score, operational mode, recipe, or external agent can override a hard gate.

## Explicit non-goals

CR-007 adds no:

- candidate-construction algorithm or random-source implementation;
- concrete uniqueness, difficulty, canonicalization, or novelty evaluator;
- puzzle-family schema, parser, rule, or solver adapter;
- generated-content database, novelty index, or negative cache;
- playable queue, CLI, UI, renderer, report, or PDF behavior;
- adaptive recipe selection or agent authority.

The checked-in `generation-contract-v1.schema.json` is the serialized exchange contract. Property-focused tests exercise representative seeds, canonical request round trips, complete accepted-artifact round trips, lineage tamper detection, duplicate rejection, and uncertainty quarantine.
