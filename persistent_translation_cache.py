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
        self._lock = threading.RLock()
        self.last_error_code = ""
        self._load()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != CACHE_SCHEMA_VERSION:
                raise ValueError("schema_version")
            entries = payload.get("entries")
            if not isinstance(entries, list):
                raise ValueError("entries")
            loaded: OrderedDict[str, dict[str, str | None]] = OrderedDict()
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
                loaded[key] = {
                    "text": text,
                    "provider": provider,
                    "model": model if isinstance(model, str) else None,
                    "requested_provider": (
                        requested_provider if isinstance(requested_provider, str) else None
                    ),
                }
            while len(loaded) > self.max_entries:
                loaded.popitem(last=False)
            with self._lock:
                self._entries = loaded
        except FileNotFoundError:
            return
        except Exception:
            with self._lock:
                self._entries.clear()
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
            self._entries[normalized_key] = record
            self._entries.move_to_end(normalized_key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            try:
                self._write_payload(self._payload_locked())
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

    def _write_payload(self, payload: Mapping[str, Any]) -> None:
        target_dir = self.path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            dir=str(target_dir),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except Exception:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
            raise