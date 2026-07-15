# Architecture Decision Records

Architecture decision records preserve why a significant technical choice was made. They are concise, reviewable, and append-only after acceptance.

## Records

- [ADR-0001: Use one Python package for the foundation](0001-single-package-foundation.md)

## Lifecycle

Statuses are Proposed, Accepted, Rejected, Deprecated, and Superseded. An accepted record is not rewritten to conceal earlier reasoning. If the decision changes, add a new record and link the supersession in both documents.

Use a decision record when a choice affects maintainability, compatibility, security, operability, or cost of reversal across the project. Local and easily reversible implementation choices do not require one.

Each record contains status, date, owner, context, decision, alternatives, consequences, risks, and reconsideration triggers.
