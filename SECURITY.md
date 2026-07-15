# Deductra Security Policy

## Supported versions

Deductra has not published a supported product release. The `0.0.0` package represents engineering foundation work and is not intended for production use.

| Version | Security support |
| --- | --- |
| `main` | Best-effort fixes during development |
| `0.0.0` | No production support |

This table will be replaced with a release support window before the first public product release.

## Report a vulnerability

Use GitHub's [private vulnerability reporting form](https://github.com/manurella/Deductra/security/advisories/new). Do not disclose a suspected vulnerability in a public issue, pull request, discussion, or social post.

If the private form is unavailable, open an issue addressed to the [verified repository owner](https://github.com/manurella) containing only a request for a secure reporting channel. Do not include vulnerability or exploit details in that issue.

Please include, when available:

- the affected revision, release, or container digest;
- the vulnerable component and expected security boundary;
- reproducible steps or a minimal proof of concept;
- the likely impact and prerequisites for exploitation;
- suggested mitigations or related advisories.

## Response process

The project aims to acknowledge a complete report within seven days and provide an initial assessment within fourteen days. These are response targets, not a service-level guarantee.

Confirmed vulnerabilities will be handled through a private advisory while a fix and disclosure plan are prepared. Credit will be offered unless the reporter prefers anonymity. Public disclosure should wait until a fix or reasonable mitigation is available.

## Security expectations

The repository uses locked dependencies, automated dependency review, vulnerability auditing, static analysis, pinned workflow actions, least-privilege automation, and non-root runtime containers. Credentials and private keys must never be committed. A leaked credential must be revoked and rotated even if it is later removed from Git history.
