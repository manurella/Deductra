# Event-Sourced Memory Projections

Last reviewed: 2026-07-16

CR-008 adds disposable read models for attempts, learning evidence, novelty fingerprints, and artifact metadata. Every view is rebuilt by pure replay from validated, immutable projection-source events. No projection is canonical evidence, and no projection may write back into puzzle, reasoning, generation, or artifact history.

## Projection-source events

Projection streams use a strict typed envelope with:

- a stable event and stream identity;
- a stream kind;
- zero-based sequence number;
- explicit schema version and timezone-aware timestamp;
- previous-event and event hashes;
- a discriminated payload.

Attempt streams cover attempt start, evaluated moves, revealed hints, viewed explanations, completion or abandonment, self-assessment, and replay views. Novelty streams record or remove accepted fingerprint entries. Artifact streams record, supersede, or remove metadata records.

Each stream is independently ordered and hash chained. Rebuild rejects gaps, duplicate event identifiers, cross-stream mixing, broken hash links, altered payloads, attempt identity changes, and interaction events after completion or abandonment. CR-008 does not add a new persistence adapter; durable ingestion of these event streams remains a later integration concern.

## Derived views

### Attempt projection

An attempt projection records status, accepted and rejected move counts, hint and explanation counts, replay views, the latest self-assessment, rule-specific evidence, all source event identifiers, and the stream head hash.

### Learning projection

The learning projection aggregates attempt evidence per user and rule. It contains observable counts and exact evidence-event references only. It deliberately contains no mastery score, confidence claim, diagnosis, personality classification, recommendation, or adaptive behavior.

### Novelty index

The novelty index contains accepted puzzle identities and the complete fingerprint set established by the generator contract. It supports exact canonical-hash lookup. Near-duplicate similarity, canonicalization, thresholds, and generation acceptance remain outside this packet.

### Artifact index

The artifact index contains identity, puzzle revision, media type, content hash, evidence and provenance references, and supersession links. It never stores raw artifact bytes and does not render reports, images, or exports.

## Rebuild contract

`rebuild_memory_projections` groups input by stream, verifies every chain, rebuilds each attempt, derives descriptive learning aggregates, and replays the single canonical novelty and artifact streams. Inputs may be enumerated in any order; stream sequence numbers determine replay order, and output records use stable semantic ordering.

Each projection and the aggregate bundle has a canonical SHA-256 hash. The checked-in contract document pairs source events with the resulting bundle and rejects any bundle that differs from a clean replay. A full rebuild therefore supports deletion and deterministic recreation without hidden checkpoint authority.

The public serialized contract is `schemas/memory-projections-v1.schema.json`.

## Explicit non-goals

CR-008 adds no:

- user interface, session navigation, or telemetry store;
- mastery model, learning analyst, recommendation system, or psychological inference;
- novelty similarity algorithm, negative cache, or generator behavior;
- report builder, renderer, PDF behavior, or artifact blob storage;
- agent memory, vector database, cloud service, or synchronization protocol;
- database migration or projection checkpoint implementation.
