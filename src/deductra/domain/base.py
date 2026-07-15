"""Shared validation policy for immutable domain models."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_serializer, field_validator


def freeze_json(value: Any) -> Any:
    """Recursively replace mutable JSON containers with immutable equivalents."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        return MappingProxyType({key: freeze_json(item) for key, item in mapping.items()})
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return tuple(freeze_json(item) for item in sequence)
    return value


def thaw_json(value: Any) -> Any:
    """Convert immutable JSON containers back to serialization-friendly values."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        return {key: thaw_json(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        sequence = cast(tuple[object, ...], value)
        return [thaw_json(item) for item in sequence]
    return value


class DomainModel(BaseModel):
    """Base class for strict, immutable, forward-compatible domain contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_assignment=True,
    )


class MetadataModel(DomainModel):
    """Base class for models carrying deeply immutable JSON metadata."""

    metadata: Mapping[str, JsonValue] = Field(default_factory=lambda: MappingProxyType({}))

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        """Prevent mutation through nested metadata containers."""
        frozen = freeze_json(value)
        if not isinstance(frozen, Mapping):  # pragma: no cover - guaranteed by field type
            raise TypeError("metadata must be a mapping")
        return cast(Mapping[str, JsonValue], frozen)

    @field_serializer("metadata")
    def serialize_metadata(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        """Emit ordinary JSON objects while retaining immutable runtime storage."""
        thawed = thaw_json(value)
        if not isinstance(thawed, dict):  # pragma: no cover - guaranteed by field type
            raise TypeError("metadata must serialize as an object")
        return cast(dict[str, Any], thawed)
