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
    "temporal_holdout",
}
_REQUIRED_ARTIFACT_IDS = {
    "vision_scheduling_benchmark",
}
_REQUIRED_CONDITION_KEYS = {
    "accuracy",
    "latency",
    "runtime",
    "repeatability",
    "temporal_holdout",
    "scheduling",
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


def _exact_value(actual: Any, expected: Any) -> bool:
    return type(actual) is type(expected) and actual == expected


def _validate_scheduling_condition(condition: Any) -> list[str]:
    if not isinstance(condition, dict):
        return ["scheduling condition must be an object"]

    expected = {
        "target_benchmark": "local_vision_request_scheduler",
        "runtime": "mock",
        "policy": "fifo_single_flight_with_queued_cancel",
        "max_inflight": 1,
        "queued_cancellation_dispatch": "first_and_latest",
        "promotion_gate": False,
        "gpu_latency_claim": False,
        "repeatability_metadata_required": True,
    }
    errors = [
        f"invalid scheduling condition: scheduling.{key}"
        for key, value in expected.items()
        if not _exact_value(condition.get(key), value)
    ]
    certified_run = condition.get("certified_run")
    if not isinstance(certified_run, dict):
        errors.append("invalid scheduling condition: scheduling.certified_run")
    else:
        expected_run = {"repeats": 10, "burst_size": 8, "work_ms": 1.0}
        for key, value in expected_run.items():
            if not _exact_value(certified_run.get(key), value):
                errors.append(f"invalid scheduling condition: scheduling.certified_run.{key}")
    return errors


def validate_scheduling_result(result: Any, condition: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(result, dict) or not isinstance(condition, dict):
        return {"ok": False, "errors": ["scheduling result and condition must be objects"]}
    expected = {
        "benchmark": condition.get("target_benchmark"),
        "runtime": condition.get("runtime"),
        "policy": condition.get("policy"),
        "max_inflight": condition.get("max_inflight"),
        "promotion_gate": condition.get("promotion_gate"),
        "gpu_latency_claim": condition.get("gpu_latency_claim"),
    }
    for key, value in expected.items():
        if not _exact_value(result.get(key), value):
            errors.append(f"scheduling result mismatch: {key}")
    certified_run = condition.get("certified_run")
    if isinstance(certified_run, dict):
        for key, value in certified_run.items():
            if not _exact_value(result.get(key), value):
                errors.append(f"scheduling result mismatch: {key}")
    burst_size = result.get("burst_size")
    if isinstance(burst_size, int) and burst_size >= 2:
        serialization = result.get("serialization")
        queued = result.get("queued_cancellation")
        if not isinstance(serialization, dict) or not isinstance(queued, dict):
            errors.append("scheduling result missing trial summaries")
        else:
            if serialization.get("valid") is not True:
                errors.append("scheduling serialization is invalid")
            if serialization.get("dispatch_order") != list(range(burst_size)):
                errors.append("scheduling serialization order mismatch")
            if queued.get("valid") is not True:
                errors.append("scheduling queued cancellation is invalid")
            if queued.get("dispatch_order") != [0, burst_size - 1]:
                errors.append("scheduling queued cancellation order mismatch")
            if queued.get("cancelled_queued") != burst_size - 2:
                errors.append("scheduling queued cancellation count mismatch")
    else:
        errors.append("scheduling result burst_size is invalid")
    return {"ok": not errors, "errors": errors}


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

    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty list")
        artifacts = []
    artifact_ids: list[str] = []
    for entry in artifacts:
        if not isinstance(entry, dict):
            errors.append("artifact entry must be an object")
            continue
        artifact_id = entry.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            errors.append("artifact id must be non-empty")
            continue
        if artifact_id in artifact_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        artifact_ids.append(artifact_id)
        relative = _safe_relative_path(entry.get("path"))
        if relative is None:
            errors.append("unsafe artifact path: " + repr(entry.get("path")))
            continue
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            errors.append(f"artifact escapes project root: {relative}")
            continue
        expected = entry.get("sha256")
        if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected.lower()):
            errors.append(f"invalid sha256 for artifact {artifact_id}")
            continue
        if not target.is_file():
            errors.append(f"artifact missing: {relative}")
            continue
        actual = _sha256_file(target)
        if actual != expected.lower():
            errors.append(f"artifact hash mismatch: {relative}")
    missing_artifacts = _REQUIRED_ARTIFACT_IDS.difference(artifact_ids)
    errors.extend(f"required artifact missing: {artifact_id}" for artifact_id in sorted(missing_artifacts))

    conditions = lock.get("conditions")
    if not isinstance(conditions, dict):
        errors.append("conditions must be an object")
    else:
        missing_conditions = _REQUIRED_CONDITION_KEYS.difference(conditions)
        errors.extend(
            f"required condition missing: {condition}"
            for condition in sorted(missing_conditions)
        )
        if "scheduling" in conditions:
            errors.extend(_validate_scheduling_condition(conditions.get("scheduling")))

    return {
        "ok": not errors,
        "errors": errors,
        "lock_id": lock.get("lock_id", ""),
        "dataset_ids": dataset_ids,
        "artifact_ids": artifact_ids,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    result = validate_benchmark_lock()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
