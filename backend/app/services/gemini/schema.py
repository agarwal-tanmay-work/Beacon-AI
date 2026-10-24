"""Structured-output helpers: Pydantic model -> Gemini JSON Schema, and tolerant JSON parsing."""

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.services.gemini.errors import GeminiMalformedResponse

# Gemini documents this subset of JSON Schema; anything else is stripped so the API cannot reject it.
_SUPPORTED_KEYS = frozenset(
    {
        "$id",
        "$defs",
        "$ref",
        "$anchor",
        "type",
        "format",
        "description",
        "enum",
        "items",
        "prefixItems",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "anyOf",
        "oneOf",
        "properties",
        "additionalProperties",
        "required",
        "propertyOrdering",
    }
)
_MAP_KEYS = ("properties", "$defs")  # values are {name: schema} - names are data, not keywords
_LIST_KEYS = ("anyOf", "oneOf", "prefixItems")


def _clean(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    if "$ref" in node:  # only "$"-prefixed siblings are allowed next to a $ref
        return {k: v for k, v in node.items() if k.startswith("$")}

    cleaned: dict[str, Any] = {}
    for key, value in node.items():
        if key not in _SUPPORTED_KEYS:
            continue
        if key in _MAP_KEYS and isinstance(value, dict):
            cleaned[key] = {name: _clean(sub) for name, sub in value.items()}
        elif key in _LIST_KEYS and isinstance(value, list):
            cleaned[key] = [_clean(sub) for sub in value]
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            cleaned[key] = _clean(value)
        else:
            cleaned[key] = value

    if isinstance(cleaned.get("properties"), dict):
        # Google recommends every field be required: optional fields are a known cause of
        # repeated / reordered output with structured responses.
        cleaned["required"] = list(cleaned["properties"])
    return cleaned


def schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for ``model`` restricted to what the Gemini API accepts."""
    return _clean(model.model_json_schema())


def _first_balanced_json(text: str) -> str | None:
    """Return the first complete ``{...}`` / ``[...]`` block in ``text`` (string-aware), if any."""
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return None
    start = min(starts)
    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_json(text: str) -> Any:
    """Parse JSON that may be wrapped in a markdown fence or surrounded by chatter."""
    cleaned = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    candidate = _first_balanced_json(cleaned)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    raise GeminiMalformedResponse("response was not valid JSON")


def make_parser[T: BaseModel](model: type[T]) -> Callable[[str], T]:
    """Parser for ``GeminiClient.generate``; validation failures count as a failed attempt (-> next model)."""

    def parse(text: str) -> T:
        data = extract_json(text)
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            # Field names only - the values may contain a reporter's words.
            fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
            raise GeminiMalformedResponse(f"response did not match schema (fields: {', '.join(fields)})") from exc

    return parse
