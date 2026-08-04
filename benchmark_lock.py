"""Validate the immutable benchmark inputs and evaluation conditions."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_LOCK_PATH = PROJECT_ROOT / "benchmarks" / "benchmark_lock.json"
_REQUIRED_DATASET_IDS = {
    "ocr_accuracy_seed",
    "manga_cover_holdout",
    "translation_e2e_contract",
}
_REQUIRED_CONDITION_KEYS = {
    "accuracy",
    "latency",
    "runtime",
    "repeatability",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lock(path: str | Path = DEFAULT_LOCK_PATH) -> dict[str, Any]:
    lock_path = Path(path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark lock must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported benchmark lock schema")
    if payload.get("status") != "locked":
        raise ValueError("benchmark lock status must be locked")
    return payload


def _safe_relative_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate


def validate_benchmark_lock(
    project_root: str | Path = PROJECT_ROOT,
    lock_path: str | Path = DEFAULT_LOCK_PATH,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[str] = []
    try:
        lock = load_lock(lock_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"lock_invalid: {type(exc).__name__}: {exc}"]}

    datasets = lock.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        errors.append("datasets must be a non-empty list")
        datasets = []
    dataset_ids: list[str] = []
    for entry in datasets:
        if not isinstance(entry, dict):
            errors.append("dataset entry must be an object")
            continue
        dataset_id = entry.get("id")
        if not isinstance(dataset_id, str) or not dataset_id:
            errors.append("dataset id must be non-empty")
            continue
        if dataset_id in dataset_ids:
            errors.append(f"duplicate dataset id: {dataset_id}")
        dataset_ids.append(dataset_id)
        relative = _safe_relative_path(entry.get("path"))
        if relative is None:
            errors.append(f"unsafe dataset path: {entry.get('path')!r}")
            continue
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            errors.append(f"dataset escapes project root: {relative}")
            continue
        expected = entry.get("sha256")
        if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected.lower()):
            errors.append(f"invalid sha256 for {dataset_id}")
            continue
        if not target.is_file():
            errors.append(f"dataset missing: {relative}")
            continue
        actual = _sha256_file(target)
        if actual != expected.lower():
            errors.append(f"dataset hash mismatch: {relative}")

    missing_ids = _REQUIRED_DATASET_IDS.difference(dataset_ids)
    errors.extend(f"required dataset missing: {dataset_id}" for dataset_id in sorted(missing_ids))

    conditions = lock.get("conditions")
    if not isinstance(conditions, dict):
        errors.append("conditions must be an object")
    else:
        missing_conditions = _REQUIRED_CONDITION_KEYS.difference(conditions)
        errors.extend(
            f"required condition missing: {condition}"
            for condition in sorted(missing_conditions)
        )

    return {
        "ok": not errors,
        "errors": errors,
        "lock_id": lock.get("lock_id", ""),
        "dataset_ids": dataset_ids,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    result = validate_benchmark_lock()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
