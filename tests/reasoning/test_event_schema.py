"""Drift test for the checked-in CR-002 event schema."""

from pathlib import Path

from deductra.reasoning.schema import rendered_event_envelope_json_schema

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_event_schema_is_current() -> None:
    schema_path = REPOSITORY_ROOT / "schemas" / "event-envelope-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == rendered_event_envelope_json_schema()
