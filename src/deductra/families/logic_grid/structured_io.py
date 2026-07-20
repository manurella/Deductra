"""Bounded structured import and deterministic export for Logic Grid drafts."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, NoReturn, cast

import yaml
from pydantic import ValidationError, model_validator
from yaml.nodes import MappingNode, ScalarNode

from deductra.domain.base import DomainModel
from deductra.domain.serialization import canonical_json
from deductra.families.logic_grid.builder import (
    LogicGridBuilderAssessment,
    LogicGridBuilderDraft,
    assess_logic_grid_builder,
    rendered_logic_grid_builder_preview,
)

STRUCTURED_IO_SCHEMA_VERSION = "1.0.0"
MAX_STRUCTURED_INPUT_BYTES = 262_144
MAX_STRUCTURED_NODES = 8_192
MAX_STRUCTURED_DEPTH = 32
MAX_STRUCTURED_COLLECTION_ITEMS = 512

_ALLOWED_YAML_TAGS = frozenset(
    {
        None,
        "!",
        "tag:yaml.org,2002:null",
        "tag:yaml.org,2002:bool",
        "tag:yaml.org,2002:int",
        "tag:yaml.org,2002:float",
        "tag:yaml.org,2002:str",
        "tag:yaml.org,2002:seq",
        "tag:yaml.org,2002:map",
    }
)


class StructuredFormat(StrEnum):
    """Supported explicit structured-document formats."""

    JSON = "json"
    YAML = "yaml"


class StructuredInputErrorCode(StrEnum):
    """Stable machine-readable reasons for rejecting structured input."""

    UNSUPPORTED_FORMAT = "unsupported_format"
    INVALID_SOURCE = "invalid_source"
    INPUT_TOO_LARGE = "input_too_large"
    INVALID_ENCODING = "invalid_encoding"
    SYNTAX_ERROR = "syntax_error"
    DUPLICATE_KEY = "duplicate_key"
    UNSAFE_FEATURE = "unsafe_feature"
    DOCUMENT_COUNT = "document_count"
    DEPTH_LIMIT = "depth_limit"
    NODE_LIMIT = "node_limit"
    COLLECTION_LIMIT = "collection_limit"
    ROOT_TYPE = "root_type"
    VALUE_TYPE = "value_type"
    SCHEMA_ERROR = "schema_error"


class StructuredInputError(DomainModel):
    """One sanitized, actionable failure at the structured-input boundary."""

    code: StructuredInputErrorCode
    path: str
    problem: str
    reason: str
    correction: str
    line: int | None = None
    column: int | None = None
    expected: str | None = None
    received: str | None = None


class LogicGridStructuredImport(DomainModel):
    """Result of parsing, validating, normalizing, and optionally proving one draft."""

    schema_version: str = STRUCTURED_IO_SCHEMA_VERSION
    format: StructuredFormat | None
    accepted: bool
    errors: tuple[StructuredInputError, ...] = ()
    draft: LogicGridBuilderDraft | None = None
    assessment: LogicGridBuilderAssessment | None = None
    normalized_preview: str | None = None

    @model_validator(mode="after")
    def validate_result_shape(self) -> LogicGridStructuredImport:
        if self.schema_version != STRUCTURED_IO_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {STRUCTURED_IO_SCHEMA_VERSION!r}")
        if self.accepted:
            if self.errors or self.draft is None or self.assessment is None:
                raise ValueError(
                    "accepted import must contain a draft and assessment without errors"
                )
            if self.normalized_preview is None:
                raise ValueError("accepted import must contain a normalized preview")
        elif not self.errors or any(
            item is not None for item in (self.draft, self.assessment, self.normalized_preview)
        ):
            raise ValueError("rejected import must contain only structured errors")
        return self


class _StructuredInputFailure(Exception):
    def __init__(self, error: StructuredInputError) -> None:
        super().__init__(error.problem)
        self.error = error


class _DuplicateKeyFailure(Exception):
    def __init__(self, key: str, line: int | None = None, column: int | None = None) -> None:
        super().__init__(key)
        self.key = key
        self.line = line
        self.column = column


class _StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader variant with unique string keys and timestamp-free scalars."""


_StrictSafeLoader.yaml_implicit_resolvers = {
    character: [resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:timestamp"]
    for character, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _construct_unique_mapping(
    loader: _StrictSafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            mark = key_node.start_mark
            raise _StructuredInputFailure(
                _error(
                    StructuredInputErrorCode.UNSAFE_FEATURE,
                    "$",
                    "The YAML document uses a merge key.",
                    "Merge keys obscure the explicit canonical object and may depend on aliases.",
                    "Write every mapping field explicitly without '<<'.",
                    line=mark.line + 1,
                    column=mark.column + 1,
                )
            )
        if not isinstance(key_node, ScalarNode) or key_node.tag != "tag:yaml.org,2002:str":
            mark = key_node.start_mark
            raise _StructuredInputFailure(
                _error(
                    StructuredInputErrorCode.VALUE_TYPE,
                    "$",
                    "A YAML object key is not a string.",
                    "Logic Grid documents use JSON-compatible string field names.",
                    "Quote the key and use a plain text field name.",
                    line=mark.line + 1,
                    column=mark.column + 1,
                    expected="string key",
                    received=key_node.tag.rpartition(":")[2],
                )
            )
        key = cast(str, loader.construct_object(key_node, deep=deep))
        if key in result:
            mark = key_node.start_mark
            raise _DuplicateKeyFailure(key, mark.line + 1, mark.column + 1)
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class _StableSafeDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def _error(
    code: StructuredInputErrorCode,
    path: str,
    problem: str,
    reason: str,
    correction: str,
    *,
    line: int | None = None,
    column: int | None = None,
    expected: str | None = None,
    received: str | None = None,
) -> StructuredInputError:
    return StructuredInputError(
        code=code,
        path=path,
        problem=problem,
        reason=reason,
        correction=correction,
        line=line,
        column=column,
        expected=expected,
        received=received,
    )


def _fail(error: StructuredInputError) -> NoReturn:
    raise _StructuredInputFailure(error)


def _rejected(
    error: StructuredInputError,
    format_: StructuredFormat | None,
) -> LogicGridStructuredImport:
    return LogicGridStructuredImport(format=format_, accepted=False, errors=(error,))


def _source_text(source: object) -> str:
    if isinstance(source, bytes):
        size = len(source)
        encoded = source
    elif isinstance(source, str):
        try:
            encoded = source.encode("utf-8")
        except UnicodeEncodeError as error:
            _fail(
                _error(
                    StructuredInputErrorCode.INVALID_ENCODING,
                    "$",
                    "The document contains invalid Unicode text.",
                    "Structured documents must have a valid UTF-8 representation.",
                    "Replace unpaired surrogate characters and retry.",
                    received=f"invalid character at offset {error.start}",
                )
            )
        size = len(encoded)
    else:
        _fail(
            _error(
                StructuredInputErrorCode.INVALID_SOURCE,
                "$",
                "The structured source is not text or bytes.",
                "The import boundary accepts a complete UTF-8 document.",
                "Provide a str or bytes value.",
                expected="str or bytes",
                received=type(source).__name__,
            )
        )
    if size > MAX_STRUCTURED_INPUT_BYTES:
        _fail(
            _error(
                StructuredInputErrorCode.INPUT_TOO_LARGE,
                "$",
                "The structured document exceeds the input limit.",
                "A byte cap prevents accidental or hostile parser resource exhaustion.",
                f"Reduce the UTF-8 document to at most {MAX_STRUCTURED_INPUT_BYTES} bytes.",
                expected=f"at most {MAX_STRUCTURED_INPUT_BYTES} bytes",
                received=f"{size} bytes",
            )
        )
    if isinstance(source, str):
        return source.removeprefix("\ufeff")
    try:
        return encoded.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        _fail(
            _error(
                StructuredInputErrorCode.INVALID_ENCODING,
                "$",
                "The document is not valid UTF-8.",
                "Structured input has one portable text encoding.",
                "Encode the document as UTF-8 and retry.",
                received=f"invalid byte at offset {error.start}",
            )
        )


def _json_depth_guard(text: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_STRUCTURED_DEPTH:
                _fail(
                    _error(
                        StructuredInputErrorCode.DEPTH_LIMIT,
                        "$",
                        "The JSON document is nested too deeply.",
                        "Bounded nesting keeps validation predictable.",
                        f"Use at most {MAX_STRUCTURED_DEPTH} collection levels.",
                        column=index + 1,
                        expected=f"depth <= {MAX_STRUCTURED_DEPTH}",
                        received=f"depth {depth}",
                    )
                )
        elif character in "]}":
            depth = max(0, depth - 1)


def _reject_nonfinite(value: str) -> NoReturn:
    raise ValueError(f"non-finite number {value}")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyFailure(key)
        result[key] = value
    return result


def _parse_json(text: str) -> Any:
    _json_depth_guard(text)
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonfinite,
        )
    except _DuplicateKeyFailure as error:
        _fail(
            _error(
                StructuredInputErrorCode.DUPLICATE_KEY,
                "$",
                f"The JSON object repeats the key {error.key!r}.",
                "Repeated keys are ambiguous and parser-dependent.",
                "Keep exactly one occurrence of every object key.",
                received="duplicate object key",
            )
        )
    except json.JSONDecodeError as error:
        _fail(
            _error(
                StructuredInputErrorCode.SYNTAX_ERROR,
                "$",
                "The JSON document is not syntactically valid.",
                error.msg,
                "Correct the indicated JSON syntax and retry.",
                line=error.lineno,
                column=error.colno,
            )
        )
    except (RecursionError, ValueError) as error:
        _fail(
            _error(
                StructuredInputErrorCode.SYNTAX_ERROR,
                "$",
                "The JSON document cannot be parsed safely.",
                str(error),
                "Use finite JSON values within the documented resource limits.",
            )
        )


def _yaml_event_guard(text: str) -> None:
    depth = 0
    nodes = 0
    documents = 0
    try:
        for event in yaml.parse(text, Loader=_StrictSafeLoader):
            event_name = type(event).__name__
            mark = getattr(event, "start_mark", None)
            line = mark.line + 1 if mark is not None else None
            column = mark.column + 1 if mark is not None else None
            if event_name == "DocumentStartEvent":
                documents += 1
                if documents > 1:
                    _fail(
                        _error(
                            StructuredInputErrorCode.DOCUMENT_COUNT,
                            "$",
                            "The YAML stream contains more than one document.",
                            "One import operation must have one unambiguous root object.",
                            "Remove additional YAML document separators and retry.",
                            line=line,
                            column=column,
                            expected="one document",
                            received=f"at least {documents} documents",
                        )
                    )
            if event_name == "AliasEvent" or getattr(event, "anchor", None) is not None:
                _fail(
                    _error(
                        StructuredInputErrorCode.UNSAFE_FEATURE,
                        "$",
                        "The YAML document uses an anchor or alias.",
                        (
                            "References can expand data unexpectedly and obscure the canonical "
                            "document."
                        ),
                        "Write each value explicitly without YAML anchors, aliases, or merges.",
                        line=line,
                        column=column,
                    )
                )
            tag = getattr(event, "tag", None)
            if tag not in _ALLOWED_YAML_TAGS:
                _fail(
                    _error(
                        StructuredInputErrorCode.UNSAFE_FEATURE,
                        "$",
                        "The YAML document uses an unsupported tag.",
                        "Only JSON-compatible standard YAML values are accepted.",
                        "Remove custom or type-specific YAML tags.",
                        line=line,
                        column=column,
                        received=str(tag),
                    )
                )
            if event_name in {"MappingStartEvent", "SequenceStartEvent", "ScalarEvent"}:
                nodes += 1
                if nodes > MAX_STRUCTURED_NODES:
                    _fail(
                        _error(
                            StructuredInputErrorCode.NODE_LIMIT,
                            "$",
                            "The YAML document contains too many values.",
                            "A node cap prevents parser resource exhaustion.",
                            f"Use at most {MAX_STRUCTURED_NODES} structured values.",
                            line=line,
                            column=column,
                            expected=f"nodes <= {MAX_STRUCTURED_NODES}",
                            received=f"more than {MAX_STRUCTURED_NODES} nodes",
                        )
                    )
            if event_name in {"MappingStartEvent", "SequenceStartEvent"}:
                depth += 1
                if depth > MAX_STRUCTURED_DEPTH:
                    _fail(
                        _error(
                            StructuredInputErrorCode.DEPTH_LIMIT,
                            "$",
                            "The YAML document is nested too deeply.",
                            "Bounded nesting keeps validation predictable.",
                            f"Use at most {MAX_STRUCTURED_DEPTH} collection levels.",
                            line=line,
                            column=column,
                            expected=f"depth <= {MAX_STRUCTURED_DEPTH}",
                            received=f"depth {depth}",
                        )
                    )
            elif event_name in {"MappingEndEvent", "SequenceEndEvent"}:
                depth -= 1
    except _StructuredInputFailure:
        raise
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        _fail(
            _error(
                StructuredInputErrorCode.SYNTAX_ERROR,
                "$",
                "The YAML document is not syntactically valid.",
                str(getattr(error, "problem", None) or "The YAML parser rejected the document."),
                "Correct the indicated YAML syntax and retry.",
                line=mark.line + 1 if mark is not None else None,
                column=mark.column + 1 if mark is not None else None,
            )
        )
    except (MemoryError, RecursionError):
        raise
    except Exception:
        _fail(
            _error(
                StructuredInputErrorCode.SYNTAX_ERROR,
                "$",
                "The YAML document cannot be parsed safely.",
                "The YAML parser rejected the document before construction.",
                "Use one JSON-compatible YAML object within the documented limits.",
            )
        )


def _parse_yaml(text: str) -> Any:
    _yaml_event_guard(text)
    try:
        return yaml.load(text, Loader=_StrictSafeLoader)
    except _DuplicateKeyFailure as error:
        _fail(
            _error(
                StructuredInputErrorCode.DUPLICATE_KEY,
                "$",
                f"The YAML object repeats the key {error.key!r}.",
                "Repeated keys are ambiguous and parser-dependent.",
                "Keep exactly one occurrence of every mapping key.",
                line=error.line,
                column=error.column,
                received="duplicate mapping key",
            )
        )
    except _StructuredInputFailure:
        raise
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        _fail(
            _error(
                StructuredInputErrorCode.SYNTAX_ERROR,
                "$",
                "The YAML document cannot be constructed safely.",
                str(getattr(error, "problem", None) or "The YAML loader rejected the document."),
                "Use one JSON-compatible YAML object without custom types.",
                line=mark.line + 1 if mark is not None else None,
                column=mark.column + 1 if mark is not None else None,
            )
        )
    except (MemoryError, RecursionError):
        raise
    except Exception:
        _fail(
            _error(
                StructuredInputErrorCode.SYNTAX_ERROR,
                "$",
                "The YAML document cannot be constructed safely.",
                "The safe YAML loader rejected the document.",
                "Use one JSON-compatible YAML object within the documented limits.",
            )
        )


def _path(parent: str, child: str | int) -> str:
    if isinstance(child, int):
        return f"{parent}[{child}]"
    return child if parent == "$" else f"{parent}.{child}"


def _validate_tree(value: Any, *, path: str = "$", depth: int = 0) -> int:
    if depth > MAX_STRUCTURED_DEPTH:
        _fail(
            _error(
                StructuredInputErrorCode.DEPTH_LIMIT,
                path,
                "The document is nested too deeply.",
                "Bounded nesting keeps model validation predictable.",
                f"Use at most {MAX_STRUCTURED_DEPTH} collection levels.",
            )
        )
    if isinstance(value, Mapping):
        if len(value) > MAX_STRUCTURED_COLLECTION_ITEMS:
            _fail(
                _error(
                    StructuredInputErrorCode.COLLECTION_LIMIT,
                    path,
                    "An object contains too many fields.",
                    "Per-collection limits prevent accidental resource exhaustion.",
                    f"Use at most {MAX_STRUCTURED_COLLECTION_ITEMS} fields.",
                    expected=f"items <= {MAX_STRUCTURED_COLLECTION_ITEMS}",
                    received=f"{len(value)} fields",
                )
            )
        nodes = 1
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(
                    _error(
                        StructuredInputErrorCode.VALUE_TYPE,
                        path,
                        "An object key is not a string.",
                        "Logic Grid documents follow the JSON object model.",
                        "Use plain text field names.",
                        expected="string key",
                        received=type(key).__name__,
                    )
                )
            nodes += _validate_tree(item, path=_path(path, key), depth=depth + 1)
            if nodes > MAX_STRUCTURED_NODES:
                _fail(
                    _error(
                        StructuredInputErrorCode.NODE_LIMIT,
                        path,
                        "The document contains too many values.",
                        "A total node cap protects model validation.",
                        f"Use at most {MAX_STRUCTURED_NODES} structured values.",
                    )
                )
        return nodes
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > MAX_STRUCTURED_COLLECTION_ITEMS:
            _fail(
                _error(
                    StructuredInputErrorCode.COLLECTION_LIMIT,
                    path,
                    "A list contains too many items.",
                    "Per-collection limits prevent accidental resource exhaustion.",
                    f"Use at most {MAX_STRUCTURED_COLLECTION_ITEMS} items.",
                    expected=f"items <= {MAX_STRUCTURED_COLLECTION_ITEMS}",
                    received=f"{len(value)} items",
                )
            )
        nodes = 1
        for index, item in enumerate(value):
            nodes += _validate_tree(item, path=_path(path, index), depth=depth + 1)
            if nodes > MAX_STRUCTURED_NODES:
                _fail(
                    _error(
                        StructuredInputErrorCode.NODE_LIMIT,
                        path,
                        "The document contains too many values.",
                        "A total node cap protects model validation.",
                        f"Use at most {MAX_STRUCTURED_NODES} structured values.",
                    )
                )
        return nodes
    if value is None or isinstance(value, (str, bool, int)):
        return 1
    if isinstance(value, float) and math.isfinite(value):
        return 1
    _fail(
        _error(
            StructuredInputErrorCode.VALUE_TYPE,
            path,
            "The document contains a non-JSON value.",
            (
                "Structured Logic Grid drafts use only objects, lists, strings, numbers, "
                "booleans, and null."
            ),
            "Replace the value with its explicit JSON-compatible representation.",
            expected="JSON-compatible value",
            received=type(value).__name__,
        )
    )


def _validation_path(location: tuple[int | str, ...]) -> str:
    path = "$"
    for part in location:
        path = _path(path, part)
    return path


def _received_description(value: Any) -> str:
    if isinstance(value, str):
        return f"string ({len(value)} characters)"
    if isinstance(value, Mapping):
        return f"object ({len(value)} fields)"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return f"list ({len(value)} items)"
    if value is None:
        return "null"
    return type(value).__name__


def _schema_errors(error: ValidationError) -> tuple[StructuredInputError, ...]:
    results: list[StructuredInputError] = []
    for detail in error.errors(include_url=False):
        error_type = str(detail["type"])
        context = detail.get("ctx") or {}
        if error_type == "missing":
            correction = "Add the required field using the builder draft schema."
        elif error_type == "extra_forbidden":
            correction = "Remove the unsupported field or move it into a documented field."
        elif error_type in {"literal_error", "union_tag_invalid"}:
            correction = "Use one of the supported literal values from the builder draft schema."
        else:
            correction = "Correct the value at this path to match the builder draft schema."
        expected_value = context.get("expected_tags", context.get("expected"))
        results.append(
            _error(
                StructuredInputErrorCode.SCHEMA_ERROR,
                _validation_path(detail["loc"]),
                "A value does not satisfy the Logic Grid builder draft schema.",
                str(detail["msg"]),
                correction,
                expected=str(expected_value) if expected_value is not None else error_type,
                received=_received_description(detail.get("input")),
            )
        )
    return tuple(results)


def import_logic_grid_builder(
    source: str | bytes,
    *,
    format: StructuredFormat | str,
    verify: bool = False,
) -> LogicGridStructuredImport:
    """Import one explicit JSON or YAML draft without leaking parser exceptions."""
    format_: StructuredFormat | None = None
    try:
        try:
            format_ = StructuredFormat(format)
        except (TypeError, ValueError):
            return _rejected(
                _error(
                    StructuredInputErrorCode.UNSUPPORTED_FORMAT,
                    "$",
                    "The requested structured format is unsupported.",
                    "Format detection is explicit so content is never interpreted ambiguously.",
                    "Choose 'json' or 'yaml'.",
                    expected="json or yaml",
                    received=str(format),
                ),
                None,
            )
        text = _source_text(source)
        value = _parse_json(text) if format_ is StructuredFormat.JSON else _parse_yaml(text)
        if not isinstance(value, Mapping):
            return _rejected(
                _error(
                    StructuredInputErrorCode.ROOT_TYPE,
                    "$",
                    "The structured document root is not an object.",
                    "A builder draft is represented by one named field object.",
                    "Wrap the draft fields in a single object or mapping.",
                    expected="object",
                    received=_received_description(value),
                ),
                format_,
            )
        _validate_tree(value)
        try:
            draft = LogicGridBuilderDraft.model_validate_json(canonical_json(value))
        except ValidationError as error:
            return LogicGridStructuredImport(
                format=format_,
                accepted=False,
                errors=_schema_errors(error),
            )
        assessment = assess_logic_grid_builder(draft, verify=verify)
        return LogicGridStructuredImport(
            format=format_,
            accepted=True,
            draft=draft,
            assessment=assessment,
            normalized_preview=rendered_logic_grid_builder_preview(assessment),
        )
    except _StructuredInputFailure as error:
        return _rejected(error.error, format_)
    except (MemoryError, RecursionError):
        return _rejected(
            _error(
                StructuredInputErrorCode.NODE_LIMIT,
                "$",
                "The structured document exceeded safe parser resources.",
                "The input could not be processed within bounded memory or nesting.",
                "Reduce the document size and structural complexity.",
            ),
            format_,
        )


def export_logic_grid_builder_json(draft: LogicGridBuilderDraft) -> str:
    """Return deterministic canonical JSON for one validated draft."""
    return canonical_json(draft) + "\n"


def export_logic_grid_builder_yaml(draft: LogicGridBuilderDraft) -> str:
    """Return deterministic, human-readable YAML without aliases or Python tags."""
    data = draft.model_dump(mode="json")
    return yaml.dump(
        data,
        Dumper=_StableSafeDumper,
        allow_unicode=True,
        default_flow_style=False,
        explicit_start=True,
        indent=2,
        line_break="\n",
        sort_keys=False,
        width=100,
    )
