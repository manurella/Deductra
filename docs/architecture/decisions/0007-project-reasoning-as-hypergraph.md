# ADR-0007: Project canonical reasoning as a directed hypergraph

- Status: Accepted
- Date: 2026-07-16
- Owner: [@manurella](https://github.com/manurella)

## Context

One deduction may depend jointly on several premises, constraints, a source state, a rule, and verifier certificates. A binary graph would split that single inference into artificial pairwise relationships, while a mutable graph authority would duplicate the event stream and create synchronization risk.

## Decision

Represent reasoning analysis as a typed directed incidence hypergraph rebuilt from immutable puzzle and trace sources. Use one many-to-many hyperedge for each deduction, stable content-derived identifiers, complete incidence closure, and canonical visual-neutral JSON. Keep the graph package dependent only on domain and reasoning contracts.

## Consequences

Reasoning structure can be exported and visualized without changing canonical history or selecting a rendering technology. Missing evidence fails during projection, and repeated projection is reproducible. Consumers must rebuild the graph when canonical sources change; direct graph edits are unsupported.

Recursive hyperedges, graph databases, custom query languages, graph learning, user interfaces, and provenance-RDF export remain outside CR-006.

## Reconsideration triggers

Create a superseding decision if scale measurements justify incremental graph persistence, or if a standards-based provenance export requires a separate typed projection.
