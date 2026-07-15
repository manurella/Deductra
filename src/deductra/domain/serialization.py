"""Canonical JSON serialization for hashing and deterministic persistence."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping
from fractions import Fraction
from typing import Any, cast

from pydantic import BaseModel


def _canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {
            unicodedata.normalize("NFC", str(key)): _canonical_value(item)
            for key, item in mapping.items()
        }
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return [_canonical_value(item) for item in sequence]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("canonical JSON does not allow NaN or infinity")
    return value


def canonical_json(value: Any) -> str:
    """Return normalized, whitespace-free JSON with deterministic key ordering."""
    return json.dumps(
        _canonical_value(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return the UTF-8 canonical representation of a supported value."""
    return canonical_json(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Return a lowercase SHA-256 digest of the canonical representation."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
