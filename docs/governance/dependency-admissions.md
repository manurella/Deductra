# Runtime Dependency Admissions

Last reviewed: 2026-07-16

Runtime dependencies require an explicit purpose, compatibility evidence, supply-chain review, and removal strategy. The uv lockfile is the reproducible dependency record; security automation audits the resolved graph.

## Pydantic

Admitted in CR-001 for strict immutable domain validation and JSON Schema generation. Its rationale remains recorded in [ADR-0002](../architecture/decisions/0002-common-core-schema.md).

## z3-solver

- Admitted version range: `>=4.16,<5`.
- Purpose: primary satisfiability checks, tracked assertions, models, and unsatisfiable-core evidence.
- Why the standard library is insufficient: it provides no SMT solver or proof-obligation engine.
- Compatibility: the admitted release provides supported CPython wheels for the project platforms; Python 3.13 and 3.14 imports and proof smoke tests run in CI.
- License and stewardship: the package distributes the Z3 solver maintained by Microsoft Research under the MIT license.
- Operational cost: native binaries materially increase installation and image size; the lockfile and security audit cover the resolved artifact graph.
- Alternatives considered: hand-built exhaustive search lacks solver evidence and scales poorly; a single CP backend would remove independent logical verification.
- Removal strategy: retain the backend protocol and replace the adapter after replaying the verification corpus with an independently reviewed solver.

## OR-Tools

- Admitted version range: `>=9.15,<10`.
- Purpose: independent integer finite-domain and solution-feasibility verification through CP-SAT.
- Why the standard library is insufficient: it provides no constraint-programming engine.
- Compatibility: the admitted release provides CPython wheels for supported platforms and versions; Python 3.13 and 3.14 imports and solver smoke tests run in CI.
- License and stewardship: OR-Tools is maintained by Google and distributed under Apache-2.0.
- Operational cost: native binaries plus numerical and data-library transitives significantly expand the resolved runtime graph.
- Alternatives considered: a second Z3 encoding would not provide the same implementation diversity; custom enumeration would be slower and harder to audit.
- Removal strategy: preserve certificate and backend protocols, introduce another independently encoded finite-domain verifier, and require corpus equivalence before removal.

## Review controls

Dependabot, locked installation, dependency review, vulnerability audit, license review, Python compatibility tests, container builds, and backend acceptance tests are the continuing controls. A missing wheel, unresolved high-severity advisory, license incompatibility, or unexplained solver disagreement blocks release.

## Jinja

- Admitted version range: `>=3.1.6,<4`.
- Purpose: strict, autoescaped rendering of semantic HTML derived from `ReportModel`.
- Why the standard library is insufficient: string assembly has no reviewed template boundary, strict undefined-value handling, or contextual HTML escaping.
- Operational controls: templates are package-local, undefined values fail closed, and rendered HTML is structurally audited.
- Removal strategy: preserve the `HtmlRenderer` protocol and prove equivalent semantic and injection-safety behavior with a replacement.

## WeasyPrint

- Admitted version: exactly `69.0`.
- Purpose: derive paged PDF artifacts from semantic HTML behind the `PdfRenderer` protocol.
- Why the standard library is insufficient: it provides no HTML/CSS pagination, tagged-PDF generation, or evidence-attachment support.
- Operational controls: the adapter denies external resource fetches, container native libraries are explicit, and profile flags never count as conformance evidence.
- Removal strategy: replace the adapter behind the protocol, then replay PDF smoke, accessibility-structure, attachment, and visual checks.
