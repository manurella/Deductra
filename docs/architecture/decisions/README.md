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

## Lifecycle

Statuses are Proposed, Accepted, Rejected, Deprecated, and Superseded. An accepted record is not rewritten to conceal earlier reasoning. If the decision changes, add a new record and link the supersession in both documents.

Use a decision record when a choice affects maintainability, compatibility, security, operability, or cost of reversal across the project. Local and easily reversible implementation choices do not require one.

Each record contains status, date, owner, context, decision, alternatives, consequences, risks, and reconsideration triggers.
