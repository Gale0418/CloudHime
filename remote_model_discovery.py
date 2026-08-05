"""Dependency-free Google Gemini model availability discovery.

This module deliberately stays separate from Qt and translation providers.  It
can be used by a background worker without making model selection or routing
synchronous with a network request.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib import error, parse, request

from model_catalog import MODEL_CATALOG, ModelSpec


MODEL_LIST_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
SNAPSHOT_SCHEMA_VERSION = 1
MAX_MODEL_LIST_PAGES = 32

DISCOVERY_STATUS_VERIFIED = "verified"
DISCOVERY_STATUS_OFFLINE_SNAPSHOT = "offline_snapshot"
DISCOVERY_STATUS_NO_KEY = "no_key"
DISCOVERY_STATUS_INVALID_KEY = "invalid_key"
DISCOVERY_STATUS_RATE_LIMITED = "rate_limited"
DISCOVERY_STATUS_UNVERIFIED = "unverified"


class RemoteModelDiscoveryError(RuntimeError):
    """A bounded, user-safe discovery failure code."""

    def __init__(self, code: str):
        self.code = str(code or "discovery_error")
        super().__init__(self.code)


@dataclass(frozen=True)
class RemoteModelCapability:
    model_id: str
    display_name: str
    supported_generation_methods: tuple[str, ...]
    supports_generate_content: bool
    supports_image_input: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "supported_generation_methods": list(self.supported_generation_methods),
            "supports_generate_content": self.supports_generate_content,
            "supports_image_input": self.supports_image_input,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RemoteModelCapability":
        model_id = normalize_model_id(payload.get("model_id"))
        methods = tuple(
            str(method).strip()
            for method in payload.get("supported_generation_methods", ())
            if str(method).strip()
        )
        if not model_id or "generateContent" not in methods:
            raise RemoteModelDiscoveryError("invalid_snapshot_model")
        return cls(
            model_id=model_id,
            display_name=str(payload.get("display_name") or model_id).strip() or model_id,
            supported_generation_methods=methods,
            supports_generate_content=True,
            supports_image_input=bool(payload.get("supports_image_input", False)),
        )


@dataclass(frozen=True)
class ModelAvailabilitySnapshot:
    captured_at: float
    api_key_fingerprint: str
    records: tuple[RemoteModelCapability, ...]
    schema_version: int = SNAPSHOT_SCHEMA_VERSION

    @property
    def available_model_ids(self) -> tuple[str, ...]:
        return tuple(record.model_id for record in self.records if record.supports_generate_content)

    def with_api_key(self, api_key: str) -> "ModelAvailabilitySnapshot":
        return replace(self, api_key_fingerprint=api_key_fingerprint(api_key))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "captured_at": float(self.captured_at),
            "api_key_fingerprint": self.api_key_fingerprint,
            "models": [record.to_dict() for record in self.records],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ModelAvailabilitySnapshot":
        if payload.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise RemoteModelDiscoveryError("invalid_snapshot_schema")
        fingerprint = str(payload.get("api_key_fingerprint") or "").strip()
        if not fingerprint:
            raise RemoteModelDiscoveryError("invalid_snapshot_fingerprint")
        raw_records = payload.get("models")
        if not isinstance(raw_records, list):
            raise RemoteModelDiscoveryError("invalid_snapshot_models")
        records = tuple(RemoteModelCapability.from_dict(item) for item in raw_records if isinstance(item, dict))
        return cls(
            captured_at=float(payload.get("captured_at")),
            api_key_fingerprint=fingerprint,
            records=records,
        )


@dataclass(frozen=True)
class ModelDiscoveryResult:
    status: str
    available_model_ids: tuple[str, ...] = ()
    records: tuple[RemoteModelCapability, ...] = ()
    snapshot: ModelAvailabilitySnapshot | None = None
    verified: bool = False
    used_snapshot: bool = False
    error_code: str = ""


def normalize_model_id(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized.startswith("models/"):
        normalized = normalized[len("models/"):]
    return normalized.strip()


def api_key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(str(api_key or "").encode("utf-8")).hexdigest()


def _catalog_by_id(model_catalog: Sequence[ModelSpec] | None) -> dict[str, ModelSpec]:
    return {spec.model_id: spec for spec in (model_catalog or MODEL_CATALOG)}


def parse_models_page(
    payload: Mapping[str, Any],
    *,
    model_catalog: Sequence[ModelSpec] | None = None,
) -> tuple[list[RemoteModelCapability], str | None]:
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        raise RemoteModelDiscoveryError("invalid_models_payload")
    catalog_by_id = _catalog_by_id(model_catalog)
    records: list[RemoteModelCapability] = []
    for raw_model in raw_models:
        if not isinstance(raw_model, Mapping):
            continue
        model_id = normalize_model_id(raw_model.get("name"))
        methods = tuple(
            str(method).strip()
            for method in raw_model.get("supportedGenerationMethods", ())
            if str(method).strip()
        )
        if not model_id or "generateContent" not in methods:
            continue
        policy = catalog_by_id.get(model_id)
        records.append(
            RemoteModelCapability(
                model_id=model_id,
                display_name=str(raw_model.get("displayName") or model_id).strip() or model_id,
                supported_generation_methods=methods,
                supports_generate_content=True,
                supports_image_input=bool(policy and policy.multimodal),
            )
        )
    next_page_token = str(payload.get("nextPageToken") or "").strip() or None
    return records, next_page_token


def fetch_remote_model_records(
    api_key: str,
    *,
    urlopen: Callable[..., Any] = request.urlopen,
    timeout_seconds: int = 10,
    endpoint: str = MODEL_LIST_ENDPOINT,
    model_catalog: Sequence[ModelSpec] | None = None,
) -> tuple[RemoteModelCapability, ...]:
    key = str(api_key or "").strip()
    if not key:
        raise RemoteModelDiscoveryError("no_key")
    records: list[RemoteModelCapability] = []
    page_token: str | None = None
    seen_tokens: set[str] = set()
    for _ in range(MAX_MODEL_LIST_PAGES):
        query: dict[str, str] = {"pageSize": "1000"}
        if page_token:
            query["pageToken"] = page_token
        separator = "&" if "?" in endpoint else "?"
        url = endpoint + separator + parse.urlencode(query)
        req = request.Request(
            url,
            headers={"Accept": "application/json", "x-goog-api-key": key},
            method="GET",
        )
        try:
            with urlopen(req, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except RemoteModelDiscoveryError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteModelDiscoveryError("invalid_models_response") from exc
        page_records, next_token = parse_models_page(payload, model_catalog=model_catalog)
        records.extend(page_records)
        if not next_token:
            break
        if next_token in seen_tokens:
            raise RemoteModelDiscoveryError("pagination_loop")
        seen_tokens.add(next_token)
        page_token = next_token
    else:
        raise RemoteModelDiscoveryError("pagination_limit")

    unique: dict[str, RemoteModelCapability] = {}
    for record in records:
        unique[record.model_id] = record
    return tuple(unique.values())


def save_availability_snapshot(path: os.PathLike[str] | str, snapshot: ModelAvailabilitySnapshot) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".model-availability-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(snapshot.to_dict(), stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def load_availability_snapshot(
    path: os.PathLike[str] | str,
    api_key: str,
) -> ModelAvailabilitySnapshot | None:
    key = str(api_key or "").strip()
    if not key:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        snapshot = ModelAvailabilitySnapshot.from_dict(payload)
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError, RemoteModelDiscoveryError):
        return None
    if snapshot.api_key_fingerprint != api_key_fingerprint(key):
        return None
    return snapshot


def _result_from_snapshot(snapshot: ModelAvailabilitySnapshot) -> ModelDiscoveryResult:
    return ModelDiscoveryResult(
        status=DISCOVERY_STATUS_OFFLINE_SNAPSHOT,
        available_model_ids=snapshot.available_model_ids,
        records=snapshot.records,
        snapshot=snapshot,
        verified=False,
        used_snapshot=True,
        error_code="offline_snapshot",
    )


def discover_remote_models(
    api_key: str,
    *,
    snapshot_path: os.PathLike[str] | str | None = None,
    urlopen: Callable[..., Any] = request.urlopen,
    timeout_seconds: int = 10,
    endpoint: str = MODEL_LIST_ENDPOINT,
    model_catalog: Sequence[ModelSpec] | None = None,
    clock: Callable[[], float] = time.time,
) -> ModelDiscoveryResult:
    key = str(api_key or "").strip()
    if not key:
        return ModelDiscoveryResult(status=DISCOVERY_STATUS_NO_KEY, error_code="no_key")
    try:
        records = fetch_remote_model_records(
            key,
            urlopen=urlopen,
            timeout_seconds=timeout_seconds,
            endpoint=endpoint,
            model_catalog=model_catalog,
        )
        snapshot = ModelAvailabilitySnapshot(
            captured_at=float(clock()),
            api_key_fingerprint=api_key_fingerprint(key),
            records=records,
        )
        snapshot_write_error = ""
        if snapshot_path is not None:
            try:
                save_availability_snapshot(snapshot_path, snapshot)
            except OSError:
                snapshot_write_error = "snapshot_write_failed"
        return ModelDiscoveryResult(
            status=DISCOVERY_STATUS_VERIFIED,
            available_model_ids=snapshot.available_model_ids,
            records=records,
            snapshot=snapshot,
            verified=True,
            error_code=snapshot_write_error,
        )
    except error.HTTPError as exc:
        if exc.code in {401, 403}:
            status = DISCOVERY_STATUS_INVALID_KEY
        elif exc.code == 429:
            status = DISCOVERY_STATUS_RATE_LIMITED
        else:
            status = DISCOVERY_STATUS_UNVERIFIED
        if status != DISCOVERY_STATUS_INVALID_KEY and snapshot_path is not None:
            snapshot = load_availability_snapshot(snapshot_path, key)
            if snapshot is not None:
                return replace(_result_from_snapshot(snapshot), error_code=status)
        return ModelDiscoveryResult(status=status, error_code=status)
    except (OSError, TimeoutError, RemoteModelDiscoveryError, ValueError, TypeError):
        if snapshot_path is not None:
            snapshot = load_availability_snapshot(snapshot_path, key)
            if snapshot is not None:
                return _result_from_snapshot(snapshot)
        return ModelDiscoveryResult(status=DISCOVERY_STATUS_UNVERIFIED, error_code="discovery_failed")


def filter_catalog_for_availability(
    catalog: Sequence[ModelSpec],
    result: ModelDiscoveryResult,
) -> tuple[ModelSpec, ...]:
    if result.status not in {DISCOVERY_STATUS_VERIFIED, DISCOVERY_STATUS_OFFLINE_SNAPSHOT}:
        return tuple(catalog)
    available = set(result.available_model_ids)
    return tuple(
        spec
        for spec in catalog
        if spec.locality == "local" or spec.model_id in available
    )

def filter_model_choices_for_availability(
    choices: Sequence[tuple[str, str]],
    result: ModelDiscoveryResult,
    *,
    model_catalog: Sequence[ModelSpec] | None = None,
    current_model: str = "",
) -> tuple[tuple[str, str], ...]:
    """Filter UI choices while preserving a currently selected unavailable model."""
    original = tuple(
        (str(label), normalize_model_id(model_id))
        for label, model_id in choices
        if normalize_model_id(model_id)
    )
    if result.status not in {DISCOVERY_STATUS_VERIFIED, DISCOVERY_STATUS_OFFLINE_SNAPSHOT}:
        return original

    available = set(result.available_model_ids)
    catalog_by_id = _catalog_by_id(model_catalog)
    visible = []
    for choice in original:
        spec = catalog_by_id.get(choice[1])
        if spec is None or spec.locality == "local" or choice[1] in available:
            visible.append(choice)

    selected = normalize_model_id(current_model)
    if selected and selected not in {model_id for _, model_id in visible}:
        selected_choice = next(
            (choice for choice in original if choice[1] == selected),
            None,
        )
        if selected_choice is not None:
            visible.append(selected_choice)
    return tuple(visible)
