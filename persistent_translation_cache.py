from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Mapping

from translation_contracts import TranslationResult


CACHE_SCHEMA_VERSION = 1
DEFAULT_MAX_ENTRIES = 512
DEFAULT_MAX_ENTRY_BYTES = 64 * 1024
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_LOAD_BYTES = 4 * 1024 * 1024


_PAYLOAD_PREFIX = (
    b'{"schema_version":'
    + str(CACHE_SCHEMA_VERSION).encode("ascii")
    + b',"entries":['
)
_PAYLOAD_SUFFIX = b"]}"
_EMPTY_PAYLOAD_BYTES = len(_PAYLOAD_PREFIX) + len(_PAYLOAD_SUFFIX)


def _entry_utf8_bytes(key: str, record: Mapping[str, str | None]) -> bytes:
    entry = {"key": key, **record}
    return json.dumps(
        entry,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _encoded_payload(entries: Mapping[str, bytes]) -> bytes:
    return _PAYLOAD_PREFIX + b",".join(entries.values()) + _PAYLOAD_SUFFIX


def _drop_oldest(
    entries: OrderedDict[str, dict[str, str | None]],
    encoded_entries: dict[str, bytes],
    payload_size: int,
) -> int:
    key, _record = entries.popitem(last=False)
    payload_size -= len(encoded_entries.pop(key))
    if entries:
        payload_size -= 1
    return payload_size


def build_translation_cache_key(context: Mapping[str, Any]) -> str:
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "context": dict(context),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PersistentTranslationCache:
    """Small fail-open AppData cache for successful primary translations."""

    def __init__(self, path: str | os.PathLike[str], *, max_entries: int = DEFAULT_MAX_ENTRIES):
        self.path = Path(path)
        self.max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[str, dict[str, str | None]] = OrderedDict()
        self._encoded_entries: dict[str, bytes] = {}
        self._total_payload_bytes = _EMPTY_PAYLOAD_BYTES
        self._lock = threading.RLock()
        self.last_error_code = ""
        self._load()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _load(self) -> None:
        try:
            with self.path.open("rb") as handle:
                raw_payload = handle.read(DEFAULT_MAX_LOAD_BYTES + 1)
            if len(raw_payload) > DEFAULT_MAX_LOAD_BYTES:
                raise ValueError("load_size_limit")
            payload = json.loads(raw_payload.decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != CACHE_SCHEMA_VERSION:
                raise ValueError("schema_version")
            entries = payload.get("entries")
            if not isinstance(entries, list):
                raise ValueError("entries")
            loaded: OrderedDict[str, dict[str, str | None]] = OrderedDict()
            encoded_entries: dict[str, bytes] = {}
            payload_size = _EMPTY_PAYLOAD_BYTES
            for item in entries:
                if not isinstance(item, dict):
                    continue
                key = item.get("key")
                text = item.get("text")
                provider = item.get("provider")
                if (
                    not isinstance(key, str)
                    or not key
                    or not isinstance(text, str)
                    or not text
                    or not isinstance(provider, str)
                    or not provider
                ):
                    continue
                model = item.get("model")
                requested_provider = item.get("requested_provider")
                record = {
                    "text": text,
                    "provider": provider,
                    "model": model if isinstance(model, str) else None,
                    "requested_provider": (
                        requested_provider if isinstance(requested_provider, str) else None
                    ),
                }
                encoded_entry = _entry_utf8_bytes(key, record)
                if len(encoded_entry) > DEFAULT_MAX_ENTRY_BYTES:
                    continue
                old_entry = encoded_entries.get(key)
                if old_entry is None:
                    if loaded:
                        payload_size += 1
                else:
                    payload_size -= len(old_entry)
                loaded[key] = record
                encoded_entries[key] = encoded_entry
                payload_size += len(encoded_entry)
                while len(loaded) > self.max_entries or payload_size > DEFAULT_MAX_TOTAL_BYTES:
                    payload_size = _drop_oldest(loaded, encoded_entries, payload_size)
            with self._lock:
                self._entries = loaded
                self._encoded_entries = encoded_entries
                self._total_payload_bytes = payload_size
        except FileNotFoundError:
            return
        except Exception:
            with self._lock:
                self._entries.clear()
                self._encoded_entries.clear()
                self._total_payload_bytes = _EMPTY_PAYLOAD_BYTES
                self.last_error_code = "load_failed"

    def get(self, key: str) -> TranslationResult | None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return None
        with self._lock:
            item = self._entries.get(normalized_key)
            if item is None:
                return None
            self._entries.move_to_end(normalized_key)
            return TranslationResult(
                text=str(item["text"]),
                provider=str(item["provider"]),
                model=item.get("model"),
                from_cache=True,
                requested_provider=item.get("requested_provider"),
            )

    def remember(
        self,
        key: str,
        result: TranslationResult,
        *,
        requested_provider: str | None = None,
    ) -> bool:
        normalized_key = str(key or "").strip()
        text = str(getattr(result, "text", "") or "").strip()
        provider = str(getattr(result, "provider", "") or "").strip()
        if not normalized_key or not text or not provider:
            return False
        record = {
            "text": text,
            "provider": provider,
            "model": (
                str(getattr(result, "model", "") or "").strip()
                or None
            ),
            "requested_provider": (
                str(requested_provider or getattr(result, "requested_provider", "") or "").strip()
                or None
            ),
        }
        with self._lock:
            try:
                encoded_entry = _entry_utf8_bytes(normalized_key, record)
            except (UnicodeEncodeError, TypeError, ValueError):
                self.last_error_code = "entry_size_limit"
                return False
            if len(encoded_entry) > DEFAULT_MAX_ENTRY_BYTES:
                self.last_error_code = "entry_size_limit"
                return False
            candidate = self._entries.copy()
            encoded_candidate = self._encoded_entries.copy()
            old_entry = encoded_candidate.get(normalized_key)
            payload_size = self._total_payload_bytes
            if old_entry is None:
                if candidate:
                    payload_size += 1
            else:
                payload_size -= len(old_entry)
            candidate[normalized_key] = record
            encoded_candidate[normalized_key] = encoded_entry
            payload_size += len(encoded_entry)
            candidate.move_to_end(normalized_key)
            while len(candidate) > self.max_entries or payload_size > DEFAULT_MAX_TOTAL_BYTES:
                payload_size = _drop_oldest(candidate, encoded_candidate, payload_size)
            if normalized_key not in candidate:
                self.last_error_code = "total_size_limit"
                return False
            encoded_candidate = {
                item_key: encoded_candidate[item_key]
                for item_key in candidate
            }
            self._entries = candidate
            self._encoded_entries = encoded_candidate
            self._total_payload_bytes = payload_size
            try:
                self._write_payload(_encoded_payload(encoded_candidate))
            except Exception:
                self.last_error_code = "write_failed"
                return False
            self.last_error_code = ""
            return True

    def _payload_locked(self) -> dict[str, Any]:
        return {
            "schema_version": CACHE_SCHEMA_VERSION,
            "entries": [
                {"key": key, **record}
                for key, record in self._entries.items()
            ],
        }

    def _write_payload(self, encoded_payload: bytes) -> None:
        if len(encoded_payload) > DEFAULT_MAX_TOTAL_BYTES:
            raise ValueError("total_size_limit")
        target_dir = self.path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            dir=str(target_dir),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded_payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except Exception:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
            raise
