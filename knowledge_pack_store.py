"""Versioned local Knowledge Pack storage with fail-open reads."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Iterable
import uuid

from settings_store import SettingsPaths, appdata_companion_path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses msvcrt.
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX uses fcntl.
    msvcrt = None


KNOWLEDGE_PACK_SCHEMA_VERSION = 1
KNOWLEDGE_PACK_DIRNAME = "knowledge_packs"
KNOWLEDGE_PACK_CATALOG_FILENAME = "catalog.json"
CATALOG_LOCK_TIMEOUT_SECONDS = 10.0
CATALOG_LOCK_POLL_SECONDS = 0.02
_PACK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class KnowledgePackValidationError(ValueError):
    """Raised when a pack cannot satisfy the local schema."""


@dataclass(frozen=True)
class KnowledgePackPaths:
    root: Path
    catalog_file: Path


@dataclass(frozen=True)
class KnowledgePackSummary:
    pack_id: str
    revision: int
    title: str
    aliases: tuple[str, ...]
    updated_at: str


def create_knowledge_pack_paths(settings_paths: SettingsPaths) -> KnowledgePackPaths:
    """Resolve the pack root beside settings, never beside the installed package."""
    root = Path(appdata_companion_path(settings_paths, KNOWLEDGE_PACK_DIRNAME))
    return KnowledgePackPaths(
        root=root,
        catalog_file=root / KNOWLEDGE_PACK_CATALOG_FILENAME,
    )


def _empty_catalog() -> dict[str, Any]:
    return {
        "schema_version": KNOWLEDGE_PACK_SCHEMA_VERSION,
        "active": None,
        "packs": [],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _validate_pack_id(pack_id: Any) -> str:
    if not isinstance(pack_id, str) or not _PACK_ID_PATTERN.fullmatch(pack_id):
        raise KnowledgePackValidationError("invalid Knowledge Pack id")
    return pack_id


def _validate_title(title: Any) -> str:
    if not isinstance(title, str):
        raise KnowledgePackValidationError("Knowledge Pack title must be text")
    normalized = title.strip()
    if not normalized:
        raise KnowledgePackValidationError("Knowledge Pack title cannot be empty")
    if len(normalized) > 240:
        raise KnowledgePackValidationError("Knowledge Pack title is too long")
    return normalized


def _validate_revision(revision: Any) -> int:
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise KnowledgePackValidationError("Knowledge Pack revision must be positive")
    return revision


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise KnowledgePackValidationError(f"{field} must be a list of text")
    return [item.strip() for item in value if item.strip()]


def _dict_list(value: Any, field: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise KnowledgePackValidationError(f"{field} must be a list of objects")
    return [dict(item) for item in value]


def build_pack_document(
    title: str,
    *,
    aliases: Iterable[str] = (),
    entries: Iterable[dict[str, Any]] = (),
    sources: Iterable[dict[str, Any]] = (),
    pack_id: str | None = None,
    revision: int = 1,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """Build the stable envelope future research/extraction stages will fill."""
    normalized_id = _validate_pack_id(pack_id or uuid.uuid4().hex)
    normalized_title = _validate_title(title)
    normalized_revision = _validate_revision(revision)
    normalized_aliases = _string_list(list(aliases), "aliases")
    normalized_entries = _dict_list(list(entries), "entries")
    normalized_sources = _dict_list(list(sources), "sources")
    timestamp = updated_at or _utc_now()
    return {
        "schema_version": KNOWLEDGE_PACK_SCHEMA_VERSION,
        "pack_id": normalized_id,
        "revision": normalized_revision,
        "title": normalized_title,
        "aliases": normalized_aliases,
        "entries": normalized_entries,
        "sources": normalized_sources,
        "created_at": created_at or timestamp,
        "updated_at": timestamp,
    }


def _pack_filename(pack_id: str, revision: int) -> str:
    normalized_id = _validate_pack_id(pack_id)
    normalized_revision = _validate_revision(revision)
    digest = hashlib.sha256(normalized_id.encode("utf-8")).hexdigest()[:12]
    return f"pack-{normalized_id.lower()}-{digest}-r{normalized_revision}.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


def _normalize_pack_document(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    try:
        if payload.get("schema_version") != KNOWLEDGE_PACK_SCHEMA_VERSION:
            return None
        pack_id = _validate_pack_id(payload.get("pack_id"))
        revision = _validate_revision(payload.get("revision"))
        title = _validate_title(payload.get("title"))
        aliases = _string_list(payload.get("aliases", []), "aliases")
        entries = _dict_list(payload.get("entries", []), "entries")
        sources = _dict_list(payload.get("sources", []), "sources")
    except KnowledgePackValidationError:
        return None
    normalized = dict(payload)
    normalized.update(
        {
            "schema_version": KNOWLEDGE_PACK_SCHEMA_VERSION,
            "pack_id": pack_id,
            "revision": revision,
            "title": title,
            "aliases": aliases,
            "entries": entries,
            "sources": sources,
        }
    )
    return normalized


class KnowledgePackStore:
    """Persist packs and a single active revision under an AppData-owned root."""

    def __init__(self, paths: KnowledgePackPaths | Path | str):
        if isinstance(paths, KnowledgePackPaths):
            self.paths = paths
        else:
            root = Path(paths)
            self.paths = KnowledgePackPaths(root=root, catalog_file=root / KNOWLEDGE_PACK_CATALOG_FILENAME)

    @contextmanager
    def _catalog_lock(self):
        self.paths.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.paths.root / ".catalog.lock"
        with lock_path.open("a+b") as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            acquired = False
            deadline = time.monotonic() + CATALOG_LOCK_TIMEOUT_SECONDS
            while not acquired:
                stream.seek(0)
                try:
                    if msvcrt is not None:
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    elif fcntl is not None:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except (BlockingIOError, OSError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("timed out waiting for Knowledge Pack catalog lock")
                    time.sleep(CATALOG_LOCK_POLL_SECONDS)
            try:
                yield
            finally:
                try:
                    stream.seek(0)
                    if msvcrt is not None:
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    elif fcntl is not None:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

    def _highest_stored_revision(self, pack_id: str) -> int:
        normalized_id = _validate_pack_id(pack_id)
        digest = hashlib.sha256(normalized_id.encode("utf-8")).hexdigest()[:12]
        prefix = f"pack-{normalized_id.lower()}-{digest}-r"
        highest = 0
        try:
            names = os.listdir(self.paths.root)
        except OSError:
            return highest
        for name in names:
            if not name.startswith(prefix) or not name.endswith(".json"):
                continue
            raw_revision = name[len(prefix):-len(".json")]
            if raw_revision.isdigit():
                highest = max(highest, int(raw_revision))
        return highest

    def save_pack(
        self,
        title: str,
        *,
        aliases: Iterable[str] = (),
        entries: Iterable[dict[str, Any]] = (),
        sources: Iterable[dict[str, Any]] = (),
        pack_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_id = _validate_pack_id(pack_id or uuid.uuid4().hex)
        with self._catalog_lock():
            catalog = self._read_catalog()
            previous = next(
                (record for record in catalog["packs"] if record["pack_id"] == normalized_id),
                None,
            )
            catalog_revision = int(previous["revision"]) if previous else 0
            revision = max(catalog_revision, self._highest_stored_revision(normalized_id)) + 1
            document = build_pack_document(
                title,
                aliases=aliases,
                entries=entries,
                sources=sources,
                pack_id=normalized_id,
                revision=revision,
            )
            pack_path = self.paths.root / _pack_filename(normalized_id, revision)
            _write_json_atomic(pack_path, document)

            record = {
                "pack_id": normalized_id,
                "revision": revision,
                "title": document["title"],
                "aliases": document["aliases"],
                "updated_at": document["updated_at"],
            }
            next_catalog = dict(catalog)
            next_catalog["packs"] = [
                item for item in catalog["packs"] if item["pack_id"] != normalized_id
            ] + [record]
            _write_json_atomic(self.paths.catalog_file, next_catalog)
            return document
    def list_packs(self) -> tuple[KnowledgePackSummary, ...]:
        catalog = self._read_catalog()
        summaries: list[KnowledgePackSummary] = []
        for record in catalog["packs"]:
            document = self.get_pack(record["pack_id"], record["revision"])
            if document is None:
                continue
            summaries.append(
                KnowledgePackSummary(
                    pack_id=document["pack_id"],
                    revision=document["revision"],
                    title=document["title"],
                    aliases=tuple(document["aliases"]),
                    updated_at=str(document.get("updated_at", "")),
                )
            )
        return tuple(summaries)

    def get_pack(self, pack_id: str, revision: int | None = None) -> dict[str, Any] | None:
        try:
            normalized_id = _validate_pack_id(pack_id)
        except KnowledgePackValidationError:
            return None
        if revision is None:
            catalog = self._read_catalog()
            record = next(
                (item for item in catalog["packs"] if item["pack_id"] == normalized_id),
                None,
            )
            if record is None:
                return None
            revision = record["revision"]
        try:
            normalized_revision = _validate_revision(revision)
        except KnowledgePackValidationError:
            return None
        path = self.paths.root / _pack_filename(normalized_id, normalized_revision)
        try:
            with path.open("r", encoding="utf-8") as stream:
                document = _normalize_pack_document(json.load(stream))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if document is None:
            return None
        if (
            document["pack_id"] != normalized_id
            or document["revision"] != normalized_revision
        ):
            return None
        return document

    def active_pack(self) -> dict[str, Any] | None:
        active = self._read_catalog().get("active")
        if not isinstance(active, dict):
            return None
        return self.get_pack(active.get("pack_id"), active.get("revision"))

    def activate(self, pack_id: str, revision: int | None = None) -> bool:
        with self._catalog_lock():
            document = self.get_pack(pack_id, revision)
            if document is None:
                return False
            catalog = self._read_catalog()
            next_catalog = dict(catalog)
            next_catalog["active"] = {
                "pack_id": document["pack_id"],
                "revision": document["revision"],
            }
            _write_json_atomic(self.paths.catalog_file, next_catalog)
            return True
    def clear_active(self) -> None:
        with self._catalog_lock():
            catalog = self._read_catalog()
            next_catalog = dict(catalog)
            next_catalog["active"] = None
            _write_json_atomic(self.paths.catalog_file, next_catalog)
    def _recover_catalog_from_files(self) -> dict[str, Any]:
        """Rebuild a non-active catalog from valid pack files after corruption."""
        records: dict[str, dict[str, Any]] = {}
        try:
            names = os.listdir(self.paths.root)
        except OSError:
            names = []
        for name in names:
            if not name.startswith("pack-") or not name.endswith(".json"):
                continue
            try:
                with (self.paths.root / name).open("r", encoding="utf-8") as stream:
                    document = _normalize_pack_document(json.load(stream))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if document is None:
                continue
            if name != _pack_filename(document["pack_id"], document["revision"]):
                continue
            record = {
                "pack_id": document["pack_id"],
                "revision": document["revision"],
                "title": document["title"],
                "aliases": document["aliases"],
                "updated_at": str(document.get("updated_at", "")),
            }
            current = records.get(record["pack_id"])
            if current is None or record["revision"] >= current["revision"]:
                records[record["pack_id"]] = record
        return {
            "schema_version": KNOWLEDGE_PACK_SCHEMA_VERSION,
            "active": None,
            "packs": list(records.values()),
        }

    def _read_catalog(self) -> dict[str, Any]:
        try:
            with self.paths.catalog_file.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return self._recover_catalog_from_files()
        if not isinstance(payload, dict) or payload.get("schema_version") != KNOWLEDGE_PACK_SCHEMA_VERSION:
            return self._recover_catalog_from_files()
        raw_packs = payload.get("packs")
        if not isinstance(raw_packs, list):
            return self._recover_catalog_from_files()

        records: dict[str, dict[str, Any]] = {}
        for raw_record in raw_packs:
            if not isinstance(raw_record, dict):
                return self._recover_catalog_from_files()
            try:
                pack_id = _validate_pack_id(raw_record.get("pack_id"))
                revision = _validate_revision(raw_record.get("revision"))
                title = _validate_title(raw_record.get("title"))
                aliases = _string_list(raw_record.get("aliases", []), "aliases")
            except KnowledgePackValidationError:
                return self._recover_catalog_from_files()
            record = {
                "pack_id": pack_id,
                "revision": revision,
                "title": title,
                "aliases": aliases,
                "updated_at": str(raw_record.get("updated_at", "")),
            }
            current = records.get(pack_id)
            if current is None or revision >= current["revision"]:
                records[pack_id] = record

        active = payload.get("active")
        normalized_active = None
        if isinstance(active, dict):
            try:
                normalized_active = {
                    "pack_id": _validate_pack_id(active.get("pack_id")),
                    "revision": _validate_revision(active.get("revision")),
                }
            except KnowledgePackValidationError:
                normalized_active = None
        return {
            "schema_version": KNOWLEDGE_PACK_SCHEMA_VERSION,
            "active": normalized_active,
            "packs": list(records.values()),
        }