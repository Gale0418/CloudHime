from __future__ import annotations

import json
import shutil
from pathlib import Path

from benchmark_lock import validate_benchmark_lock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = PROJECT_ROOT / "benchmarks" / "benchmark_lock.json"
DATASET_NAMES = (
    "ocr_accuracy_cases.json",
    "manga_cover_cases.json",
    "temporal_holdout_cases.json",
    "translation_e2e_cases.json",
)


def _copy_lock_fixture(tmp_path: Path) -> Path:
    benchmark_root = tmp_path / "benchmarks"
    benchmark_root.mkdir()
    for name in DATASET_NAMES:
        shutil.copy2(PROJECT_ROOT / "benchmarks" / name, benchmark_root / name)
    lock_path = benchmark_root / "benchmark_lock.json"
    shutil.copy2(LOCK_PATH, lock_path)
    return lock_path


def test_benchmark_lock_matches_current_manifests():
    result = validate_benchmark_lock(PROJECT_ROOT, LOCK_PATH)

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["dataset_ids"] == [
        "ocr_accuracy_seed",
        "manga_cover_holdout",
        "translation_e2e_contract",
        "temporal_holdout",
    ]


def test_benchmark_lock_rejects_manifest_mutation(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    manifest = tmp_path / "benchmarks" / "ocr_accuracy_cases.json"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any("dataset hash mismatch" in error for error in result["errors"])


def test_benchmark_lock_rejects_unsafe_dataset_path(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    payload["datasets"][0]["path"] = "../outside.json"
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any("unsafe dataset path" in error for error in result["errors"])


def test_benchmark_lock_requires_repeatability_and_runtime_conditions(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    del payload["conditions"]["repeatability"]
    del payload["conditions"]["runtime"]
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert "required condition missing: repeatability" in result["errors"]
    assert "required condition missing: runtime" in result["errors"]


def test_benchmark_lock_requires_temporal_holdout_condition(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    del payload["conditions"]["temporal_holdout"]
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert "required condition missing: temporal_holdout" in result["errors"]
