# Directed Reasoning Hypergraph

Last reviewed: 2026-07-16

CR-006 adds a typed directed incidence hypergraph as a deterministic read-only projection. The immutable puzzle specification and canonical human solve trace remain authoritative. The graph is never edited directly and introduces no graph database, query language, visual layout, renderer, or autonomous mutation.

## Model

A vertex records a stable identifier, required semantic type, canonical source identity, content hash, and visual-neutral attributes. A directed hyperedge records one typed many-to-many relationship with sorted tail and head incidence sets. The public catalog includes the complete v0.1 vertex and edge vocabularies even though CR-006 currently projects only source types that exist.

Static projection creates puzzle, domain, value, variable, constraint, and clue vertices plus domain-membership, constraint-incidence, and explanatory edges. Verified human deductions create vertices for source and result states, events, rules, premise and conclusion atoms, supporting constraints, and certificate identities. One assignment or elimination remains one hyperedge rather than being fragmented into pairwise links.

## Determinism

Vertex identifiers derive only from vertex type and immutable source identity. Edge identifiers derive only from type, source identity, and sorted incidence sets. The final vertex and edge collections are sorted before the graph is sealed with a canonical SHA-256 digest. Repeated projection of identical sources therefore produces byte-identical visual-neutral JSON.

Operational timing, registration order, coordinates, colors, labels chosen by a renderer, and other presentation state do not affect graph identity.

## Evidence closure

Every tail and head reference must resolve to a vertex in the same graph. Verified deduction attempts must resolve their event, source state, result state, rule, premises, conclusions, supporting constraints, and certificate identities before an edge is emitted. Construction fails if evidence is incomplete or if stable identities conflict.

Certificate vertices represent certificate identities carried by the canonical trace. Full certificate contents and integrity remain governed by the separate VerificationRecord contract.

The serialized contract is [Reasoning Hypergraph v1](../../schemas/reasoning-hypergraph-v1.schema.json). Canonical export contains data only and is independent of any future visualization technology.
