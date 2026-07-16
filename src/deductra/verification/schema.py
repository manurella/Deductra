"""JSON Schema projection for the canonical verification record."""

from __future__ import annotations

import json
from typing import Any

from deductra.verification.contracts import VerificationRecord


def verification_record_json_schema() -> dict[str, Any]:
    """Return the versioned VerificationRecord JSON Schema."""
    schema = VerificationRecord.model_json_schema()
    schema["$id"] = "urn:deductra:schema:verification-record:1"
    schema["title"] = "Deductra Verification Record v1"
    return schema


def rendered_verification_record_json_schema() -> str:
    """Return the normalized checked-in verification schema representation."""
    return (
        json.dumps(
            verification_record_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
