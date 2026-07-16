"""JSON Schema projection for canonical reasoning events."""

from __future__ import annotations

import json
from typing import Any

from deductra.reasoning.events import EventEnvelope


def event_envelope_json_schema() -> dict[str, Any]:
    """Return the versioned EventEnvelope JSON Schema."""
    schema = EventEnvelope.model_json_schema()
    schema["$id"] = "urn:deductra:schema:event-envelope:1"
    schema["title"] = "Deductra Event Envelope v1"
    return schema


def rendered_event_envelope_json_schema() -> str:
    """Return the normalized checked-in event schema representation."""
    return (
        json.dumps(
            event_envelope_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
