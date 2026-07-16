"""Validate the repository's public Markdown documentation."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCUMENTS = {
    Path("CODE_OF_CONDUCT.md"),
    Path("CONTRIBUTING.md"),
    Path("README.md"),
    Path("SECURITY.md"),
    Path("docs/README.md"),
    Path("docs/architecture/README.md"),
    Path("docs/architecture/core-domain-contracts.md"),
    Path("docs/architecture/event-protocol-and-store.md"),
    Path("docs/architecture/state-reduction-and-replay.md"),
    Path("docs/architecture/verification-contracts-and-backends.md"),
    Path("docs/architecture/dependency-rules.md"),
    Path("docs/architecture/decisions/0001-single-package-foundation.md"),
    Path("docs/architecture/decisions/0002-common-core-schema.md"),
    Path("docs/architecture/decisions/0003-canonical-event-store.md"),
    Path("docs/architecture/decisions/0004-immutable-state-reduction.md"),
    Path("docs/architecture/decisions/0005-independent-proof-verification.md"),
    Path("docs/architecture/decisions/README.md"),
    Path("docs/architecture/overview.md"),
    Path("docs/governance/README.md"),
    Path("docs/governance/current-state.md"),
    Path("docs/governance/dependency-admissions.md"),
    Path("docs/governance/decision-log.md"),
    Path("docs/governance/project-governance.md"),
    Path("docs/governance/risk-register.md"),
}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
URI_SCHEMES = {"data", "http", "https", "mailto"}


def markdown_files() -> list[Path]:
    """Return tracked Markdown plus required documents awaiting their first commit."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--", "*.md"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = {Path(line) for line in result.stdout.splitlines() if line}
    return sorted(
        REPOSITORY_ROOT / path
        for path in tracked | REQUIRED_DOCUMENTS
        if (REPOSITORY_ROOT / path).is_file()
    )


def link_path(source: Path, raw_target: str) -> Path | None:
    """Resolve a local Markdown target, or return None for non-file links."""
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]

    parsed = urlsplit(target)
    if parsed.scheme.lower() in URI_SCHEMES or not parsed.path:
        return None

    decoded = unquote(parsed.path)
    candidate = (
        REPOSITORY_ROOT / decoded.lstrip("/")
        if decoded.startswith("/")
        else source.parent / decoded
    )
    return candidate.resolve()


def validate_document(path: Path) -> list[str]:
    """Return structural and local-link errors for one Markdown document."""
    relative = path.relative_to(REPOSITORY_ROOT)
    content = path.read_text(encoding="utf-8")
    errors: list[str] = []

    if content and not content.endswith("\n"):
        errors.append(f"{relative}: file must end with a newline")

    first_content_line = next((line for line in content.splitlines() if line.strip()), "")
    if re.fullmatch(r"#{1,6} .+", first_content_line) is None:
        errors.append(f"{relative}: first content line must be a Markdown heading")

    for line_number, line in enumerate(content.splitlines(), start=1):
        for match in MARKDOWN_LINK.finditer(line):
            resolved = link_path(path, match.group("target"))
            if resolved is None:
                continue
            try:
                resolved.relative_to(REPOSITORY_ROOT)
            except ValueError:
                errors.append(f"{relative}:{line_number}: link escapes the repository")
                continue
            if not resolved.exists():
                errors.append(
                    f"{relative}:{line_number}: missing local link target '{match.group('target')}'"
                )

    return errors


def main() -> int:
    """Validate required documents and all public Markdown files."""
    errors = [
        f"missing required document: {path.as_posix()}"
        for path in sorted(REQUIRED_DOCUMENTS)
        if not (REPOSITORY_ROOT / path).is_file()
    ]
    documents = markdown_files()
    for document in documents:
        errors.extend(validate_document(document))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"validated {len(documents)} Markdown document(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
