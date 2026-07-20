# Architecture Decision Records

Architecture decision records preserve why a significant technical choice was made. They are concise, reviewable, and append-only after acceptance.

## Records

- [ADR-0001: Use one Python package for the foundation](0001-single-package-foundation.md)
- [ADR-0002: Establish a common immutable core schema](0002-common-core-schema.md)
- [ADR-0003: Persist canonical events in tamper-evident SQLite streams](0003-canonical-event-store.md)
- [ADR-0004: Derive immutable state through retained branch projections](0004-immutable-state-reduction.md)
- [ADR-0005: Verify deductions through independent solver encodings](0005-independent-proof-verification.md)
- [ADR-0006: Separate human rule proposals from verification authority](0006-verified-human-reasoning-loop.md)
- [ADR-0007: Project canonical reasoning as a directed hypergraph](0007-project-reasoning-as-hypergraph.md)
- [ADR-0008: Gate generation on deterministic evidence](0008-gate-generation-on-deterministic-evidence.md)
- [ADR-0009: Derive memory views from immutable events](0009-derive-memory-views-from-events.md)
- [ADR-0010: Keep agents optional and non-authoritative](0010-keep-agents-optional-and-non-authoritative.md)
- [ADR-0011: Specialize families through the common puzzle specification](0011-specialize-families-through-common-specifications.md)
- [ADR-0012: Encode Logic Equations independently in Z3 and CP-SAT](0012-encode-logic-equations-independently.md)
- [ADR-0013: Model Logic Grid as anchor-aligned bijections](0013-model-logic-grid-as-anchor-aligned-bijections.md)
- [ADR-0014: Encode Logic Grid independently in Z3 and CP-SAT](0014-encode-logic-grid-independently.md)
- [ADR-0015: Keep guided authoring presentation-neutral](0015-keep-guided-authoring-presentation-neutral.md)
- [ADR-0016: Bound structured authoring input before model validation](0016-bound-structured-authoring-input.md)
- [ADR-0017: Retain play history without granting proof authority](0017-retain-play-history-without-proof-authority.md)
- [ADR-0018: Separate validation disclosure from proof](0018-separate-validation-disclosure-from-proof.md)

## Lifecycle

Statuses are Proposed, Accepted, Rejected, Deprecated, and Superseded. An accepted record is not rewritten to conceal earlier reasoning. If the decision changes, add a new record and link the supersession in both documents.

Use a decision record when a choice affects maintainability, compatibility, security, operability, or cost of reversal across the project. Local and easily reversible implementation choices do not require one.

Each record contains status, date, owner, context, decision, alternatives, consequences, risks, and reconsideration triggers.
