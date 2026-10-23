"""Strict, non-activating extraction contract for Knowledge Pack candidates."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Any, Iterable

EXTRACTION_SCHEMA_VERSION = 1
PROMOTION_CONFIDENCE = 0.75
MAX_ENTRIES = 100
MAX_ALIASES = 20
MAX_SOURCE_IDS = 20
MAX_TEXT_LENGTH = 2_000
MAX_RESPONSE_LENGTH = 200_000
MAX_JSON_DEPTH = 20
_SOURCE_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_CODE_BLOCK_PATTERN = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)
_TOP_LEVEL_KEYS = {"schema_version", "title", "aliases", "entries"}
_ENTRY_KEYS = {"name", "aliases", "kind", "description", "confidence", "source_ids"}
_ALIAS_KEYS = {"text", "confidence", "source_ids"}
_ALLOWED_KINDS = {"character", "term", "place", "organization", "item", "other"}


class ExtractionValidationError(ValueError):
    """Raised when model output cannot satisfy the extraction contract."""


def _text(value: Any, field: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ExtractionValidationError(f"{field} must be text")
    if any(
        unicodedata.category(char) in {"Cc", "Cf", "Cs"} and char not in "\t\n\r"
        for char in value
    ):
        raise ExtractionValidationError(f"{field} contains an unsupported Unicode control character")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.split())
    if required and not normalized:
        raise ExtractionValidationError(f"{field} must not be empty")
    if len(normalized) > MAX_TEXT_LENGTH:
        raise ExtractionValidationError(f"{field} is too long")
    return normalized


def _key(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).casefold())


def _text_list(value: Any, field: str, *, maximum: int = MAX_ALIASES) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ExtractionValidationError(f"{field} must be a bounded list of text")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _text(item, field, required=True)
        key = _key(normalized)
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _confidence(value: Any, field: str = "confidence") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ExtractionValidationError(f"{field} must be a finite number from 0 to 1")
    return float(value)


def _source_ids(value: Any, allowed: set[str]) -> list[str]:
    if not isinstance(value, list) or not 0 < len(value) <= MAX_SOURCE_IDS:
        raise ExtractionValidationError("source_ids must be a bounded non-empty list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not _SOURCE_ID_PATTERN.fullmatch(item):
            raise ExtractionValidationError("source_ids contain an invalid id")
        if item not in allowed:
            raise ExtractionValidationError("source_ids reference an unknown source")
        if item not in result:
            result.append(item)
    return result


def _validate_alias(value: Any, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _ALIAS_KEYS:
        raise ExtractionValidationError("alias contains unknown or missing fields")
    return {
        "text": _text(value["text"], "alias text", required=True),
        "confidence": _confidence(value["confidence"], "alias confidence"),
        "source_ids": _source_ids(value["source_ids"], allowed),
    }


def _validate_entry(value: Any, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExtractionValidationError("entry must be an object")
    if set(value) != _ENTRY_KEYS:
        raise ExtractionValidationError("entry contains unknown or missing fields")
    name = _text(value["name"], "entry name", required=True)
    kind = _text(value["kind"], "entry kind", required=True).casefold()
    if kind not in _ALLOWED_KINDS:
        raise ExtractionValidationError("entry kind is not allowed")
    return {
        "name": name,
        "aliases": _text_list(value["aliases"], "entry aliases"),
        "kind": kind,
        "description": _text(value["description"], "entry description", required=True),
        "confidence": _confidence(value["confidence"], "entry confidence"),
        "source_ids": _source_ids(value["source_ids"], allowed),
    }


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExtractionValidationError("extraction response contains a duplicate JSON key")
        result[key] = value
    return result


def _ensure_json_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ExtractionValidationError("extraction response JSON is too deeply nested")
    if isinstance(value, dict):
        for child in value.values():
            _ensure_json_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _ensure_json_depth(child, depth + 1)


def parse_extraction_response(raw: str | bytes) -> dict[str, Any]:
    """Parse only a bounded complete JSON object, optionally in one JSON fence."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_RESPONSE_LENGTH:
            raise ExtractionValidationError("extraction response is too large")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExtractionValidationError("extraction response must be UTF-8") from exc
    elif isinstance(raw, str):
        text = raw
        if len(text.encode("utf-8")) > MAX_RESPONSE_LENGTH:
            raise ExtractionValidationError("extraction response is too large")
    else:
        raise ExtractionValidationError("extraction response must be text")
    text = text.strip()
    match = _CODE_BLOCK_PATTERN.fullmatch(text)
    if match:
        text = match.group(1).strip()
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except ExtractionValidationError:
        raise
    except RecursionError as exc:
        raise ExtractionValidationError("extraction response JSON is too deeply nested") from exc
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ExtractionValidationError("extraction response is not valid JSON") from exc
    _ensure_json_depth(payload)
    if not isinstance(payload, dict):
        raise ExtractionValidationError("extraction response must be a JSON object")
    return payload


def validate_extraction_payload(
    value: Any,
    *,
    allowed_source_ids: Iterable[str],
    expected_title: str | None = None,
) -> dict[str, Any]:
    """Validate model output against source ids from a trusted research draft."""
    if not isinstance(value, dict):
        raise ExtractionValidationError("extraction payload must be an object")
    if set(value) != _TOP_LEVEL_KEYS or type(value.get("schema_version")) is not int or value.get("schema_version") != EXTRACTION_SCHEMA_VERSION:
        raise ExtractionValidationError("extraction payload has an invalid schema")
    title = _text(value["title"], "title", required=True)
    if expected_title is not None and _key(title) != _key(_text(expected_title, "expected title", required=True)):
        raise ExtractionValidationError("extraction title does not match the requested work")
    entries = value["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ExtractionValidationError("entries must be a bounded list")
    allowed = {item for item in allowed_source_ids if isinstance(item, str) and _SOURCE_ID_PATTERN.fullmatch(item)}
    aliases = value["aliases"]
    if not isinstance(aliases, list) or len(aliases) > MAX_ALIASES:
        raise ExtractionValidationError("aliases must be a bounded list")
    normalized_aliases = [_validate_alias(item, allowed) for item in aliases]
    normalized_entries = [_validate_entry(item, allowed) for item in entries]
    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "title": title,
        "aliases": normalized_aliases,
        "entries": normalized_entries,
    }


def _entry_keys(entry: dict[str, Any]) -> set[str]:
    return {_key(entry["name"]), *(_key(alias) for alias in entry["aliases"])}


def _merge_aliases(aliases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for alias in aliases:
        groups.setdefault(_key(alias["text"]), []).append(alias)
    return [
        {
            "text": group[0]["text"],
            "confidence": max(item["confidence"] for item in group),
            "source_ids": sorted({source_id for item in group for source_id in item["source_ids"]}),
        }
        for _, group in sorted(groups.items())
    ]


def merge_extraction_candidates(
    payloads: Iterable[Any],
    *,
    allowed_source_ids: Iterable[str],
    expected_title: str,
) -> dict[str, Any]:
    """Merge safe candidates while keeping low-confidence/conflicting claims out."""
    allowed = set(allowed_source_ids)
    title = _text(expected_title, "expected title", required=True)
    accepted: list[dict[str, Any]] = []
    accepted_aliases: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for index, payload in enumerate(payloads):
        try:
            normalized = validate_extraction_payload(
                payload,
                allowed_source_ids=allowed,
                expected_title=title,
            )
        except ExtractionValidationError as exc:
            rejected.append({"index": str(index), "reason": "invalid_payload", "detail": str(exc)})
            continue
        for alias in normalized["aliases"]:
            if alias["confidence"] < PROMOTION_CONFIDENCE:
                rejected.append({"index": str(index), "reason": "low_confidence_alias", "detail": alias["text"]})
            else:
                accepted_aliases.append(alias)
        for entry in normalized["entries"]:
            if entry["confidence"] < PROMOTION_CONFIDENCE:
                rejected.append({"index": str(index), "reason": "low_confidence", "detail": entry["name"]})
            else:
                accepted.append(entry)

    groups: list[list[dict[str, Any]]] = []
    group_keys: list[set[str]] = []
    for entry in accepted:
        keys = _entry_keys(entry)
        matching = [index for index, known in enumerate(group_keys) if keys & known]
        if not matching:
            groups.append([entry])
            group_keys.append(set(keys))
            continue
        first = matching[0]
        groups[first].append(entry)
        group_keys[first].update(keys)
        for duplicate in reversed(matching[1:]):
            groups[first].extend(groups.pop(duplicate))
            group_keys[first].update(group_keys.pop(duplicate))

    merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for group in sorted(groups, key=lambda items: _key(items[0]["name"])):
        signatures = {(_key(item["description"]), item["kind"]) for item in group}
        if len(signatures) > 1:
            conflicts.append({
                "name": group[0]["name"],
                "source_ids": sorted({source_id for item in group for source_id in item["source_ids"]}),
                "reason": "conflicting_claims",
            })
            continue
        first = group[0]
        merged_entry_aliases: list[str] = []
        for item in group:
            for alias in [item["name"], *item["aliases"]]:
                if _key(alias) not in {_key(value) for value in merged_entry_aliases}:
                    merged_entry_aliases.append(alias)
        identity = _key(first["name"])
        merged.append({
            "name": first["name"],
            "aliases": [alias for alias in merged_entry_aliases if _key(alias) != identity],
            "kind": first["kind"],
            "description": first["description"],
            "confidence": max(item["confidence"] for item in group),
            "source_ids": sorted({source_id for item in group for source_id in item["source_ids"]}),
        })
    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "status": "candidate",
        "title": title,
        "aliases": _merge_aliases(accepted_aliases),
        "entries": merged,
        "rejected": rejected,
        "conflicts": conflicts,
        "owner_confirmed": False,
    }