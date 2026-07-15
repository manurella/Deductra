"""Validate Conventional Commit headers for future repository changes."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

ALLOWED_TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)
PACKET = r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3}"
HEADER = re.compile(
    rf"^(?P<type>{'|'.join(ALLOWED_TYPES)})"
    r"\((?P<scope>[a-z0-9][a-z0-9._/-]*)\)"
    r"(?P<breaking>!)?: "
    rf"(?P<subject>[a-z0-9][^\r\n]*?)(?: \[(?P<packet>{PACKET})\])?$"
)
MAX_HEADER_LENGTH = 100


def validate_message(message: str) -> list[str]:
    """Return human-readable violations for one commit message."""
    header = message.splitlines()[0].strip() if message.strip() else ""
    errors: list[str] = []

    if not header:
        return ["commit message is empty"]
    if len(header) > MAX_HEADER_LENGTH:
        errors.append(f"header exceeds {MAX_HEADER_LENGTH} characters")

    match = HEADER.fullmatch(header)
    if match is None:
        errors.append(
            "header must match 'type(scope): imperative subject' with an optional "
            "'[PACKET-ID]' suffix"
        )
        return errors

    subject = match.group("subject")
    if subject.endswith("."):
        errors.append("subject must not end with a period")

    if match.group("breaking") and "BREAKING CHANGE:" not in message:
        errors.append("breaking commits must include a 'BREAKING CHANGE:' footer")

    return errors


def messages_in_range(revision_range: str) -> list[tuple[str, str]]:
    """Read non-merge commit messages from a Git revision range."""
    result = subprocess.run(
        ["git", "rev-list", "--reverse", "--no-merges", revision_range],
        check=True,
        capture_output=True,
        text=True,
    )
    commits = [line for line in result.stdout.splitlines() if line]
    messages: list[tuple[str, str]] = []
    for commit in commits:
        message = subprocess.run(
            ["git", "show", "--no-patch", "--format=%B", commit],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        messages.append((commit, message))
    return messages


def parse_args() -> argparse.Namespace:
    """Parse one validation source from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--message")
    sources.add_argument("--commit-msg-file", type=Path)
    sources.add_argument("--range", dest="revision_range")
    return parser.parse_args()


def main() -> int:
    """Validate the selected message source and return a shell status."""
    args = parse_args()
    direct_message = cast(str | None, args.message)
    commit_msg_file = cast(Path | None, args.commit_msg_file)
    revision_range = cast(str | None, args.revision_range)

    if direct_message is not None:
        messages = [("message", direct_message)]
    elif commit_msg_file is not None:
        messages = [(str(commit_msg_file), commit_msg_file.read_text(encoding="utf-8"))]
    elif revision_range is not None:
        messages = messages_in_range(revision_range)
    else:  # pragma: no cover - argparse guarantees a source
        raise AssertionError("missing validation source")

    violations = 0
    for identifier, message in messages:
        errors = validate_message(message)
        for error in errors:
            print(f"{identifier}: {error}", file=sys.stderr)
        violations += len(errors)

    if violations:
        return 1

    print(f"validated {len(messages)} Conventional Commit message(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
