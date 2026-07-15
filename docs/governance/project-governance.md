# Project Governance

Last reviewed: 2026-07-15

## Purpose and scope

Deductra is governed as a public, reviewable software project. This policy covers repository stewardship, engineering changes, documentation, releases, security, and community participation.

The M0 milestone establishes the project foundation only. Product capabilities require separately reviewed changes and must not be introduced through foundation work.

## Authority and stewardship

The verified repository owner, [@manurella](https://github.com/manurella), is the final decision owner while Deductra remains a single-owner project. Contributors may propose changes and reviewers may recommend approval, but merge and release authority remains with the repository owner unless delegation is recorded publicly.

The following sources govern their respective subjects:

1. [LICENSE](../../LICENSE) governs use and distribution.
2. [SECURITY.md](../../SECURITY.md) governs vulnerability disclosure.
3. [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md) governs community conduct.
4. This document governs project change and stewardship.
5. Accepted [architecture decision records](../architecture/decisions/README.md) govern significant technical decisions.
6. Other architecture documents and [CONTRIBUTING.md](../../CONTRIBUTING.md) provide implementation and contribution contracts.

When two technical documents conflict, the most recent accepted decision record controls. Conflicts involving licensing, security disclosure, or conduct are resolved by their dedicated root policy.

## Change model

Development follows short-lived branches and reviewable pull requests. Each change should deliver one coherent outcome, state what is out of scope, and include evidence proportionate to its risk.

Changes are classified as:

- **Editorial:** wording, formatting, or link corrections with no contract change.
- **Local implementation:** a bounded implementation that does not alter a public or architectural contract.
- **Contract change:** a change to a public interface, dependency rule, data format, release artifact, or cross-module boundary. It requires architecture-decision consideration and a migration or compatibility assessment.
- **Foundation change:** a change to project scope, governance, supported platforms, packaging model, security posture, or release definition. It requires an explicit proposal, impact analysis, and owner approval.

Accepted policy and architecture history is amended through new decisions. It is not silently rewritten to hide earlier reasoning.

## Pull requests and review

Pull requests must describe the objective, scope, validation evidence, architecture impact, risks, and rollback. Required automated checks must pass and review conversations must be resolved before merge.

Squash merge is the default. A history-preserving merge may be used when individual commits carry durable diagnostic or release value. Direct changes to `main` should be prevented with repository rules once required checks are established.

High-risk security, verification, migration, or release changes require an independent review or equivalent differential evidence.

## Commit policy

Every commit in public history uses a scoped Conventional Commit header:

```text
type(scope): imperative subject
```

An optional work identifier may be appended in square brackets. Commits should be understandable, bounded, and testable at their intended checkpoint. Temporary or ambiguous subjects are not acceptable in final public history.

## Documentation governance

Each durable fact has one canonical home. Summary documents link to policy rather than duplicating it. A change that alters behavior or a contract must update the corresponding specification, decision record, contributor guidance, or user documentation in the same pull request.

Internal Markdown links are checked automatically. External links are reviewed deliberately because making network access a pull-request requirement would introduce avoidable instability.

The [current-state document](current-state.md) is concise and forward-looking. The [decision log](decision-log.md) records accepted rulings. Significant and costly-to-reverse technical choices receive a dedicated architecture decision record.

## Dependencies and supply chain

Runtime dependencies require a documented purpose, maintenance and license review, supported-platform assessment, alternatives, and removal strategy. Dependencies are locked with uv and updated through reviewed changes.

Automation follows least privilege. Third-party workflow actions are pinned to immutable commit SHAs. Secrets are supplied through the hosting platform and must not be embedded in source, images, logs, or build artifacts.

## Releases

Releases use semantic version tags and originate from a commit reachable from `main`. A release must pass required quality, compatibility, security, packaging, and container checks.

M0 publishes wheel and source-distribution artifacts to GitHub Releases and a non-root runtime image to GHCR. PyPI publication is not part of M0. Release artifacts and container images receive provenance attestations through the repository workflow.

## Recovery and reversal

Recovery prefers, in order, reverting the offending change, restoring a known tagged checkpoint, or applying a forward migration. Public history is not deleted merely to obtain a cleaner starting point.

## Policy review

Governance is reviewed at each milestone, after a material security or release incident, or when the ownership model changes. Proposed changes must update the decision log and identify affected policies, checks, and migration needs.
