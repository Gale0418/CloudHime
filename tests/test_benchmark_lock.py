from __future__ import annotations

import json
import shutil
from pathlib import Path

from benchmark_lock import load_lock, validate_benchmark_lock, validate_scheduling_result
import vision_scheduling_benchmark as scheduling_benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = PROJECT_ROOT / "benchmarks" / "benchmark_lock.json"
DATASET_NAMES = (
    "ocr_accuracy_cases.json",
    "manga_cover_cases.json",
    "temporal_holdout_cases.json",
    "translation_e2e_cases.json",
)
ARTIFACT_NAMES = ("vision_scheduling_benchmark.py", "translation_e2e_benchmark.py")


def _copy_lock_fixture(tmp_path: Path) -> Path:
    benchmark_root = tmp_path / "benchmarks"
    benchmark_root.mkdir()
    for name in DATASET_NAMES:
        shutil.copy2(PROJECT_ROOT / "benchmarks" / name, benchmark_root / name)
    for name in ARTIFACT_NAMES:
        shutil.copy2(PROJECT_ROOT / name, tmp_path / name)
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
    assert result["artifact_ids"] == ["vision_scheduling_benchmark", "translation_e2e_evaluator"]


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

def test_benchmark_lock_requires_scheduling_condition(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    del payload["conditions"]["scheduling"]
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert "required condition missing: scheduling" in result["errors"]


def test_benchmark_lock_requires_scheduling_artifact(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    payload["artifacts"] = []
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any("required artifact missing: vision_scheduling_benchmark" in error for error in result["errors"])

def test_benchmark_lock_rejects_scheduling_contract_mutation(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    payload["conditions"]["scheduling"]["max_inflight"] = 2
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any("scheduling.max_inflight" in error for error in result["errors"])


def test_benchmark_lock_rejects_boolean_scheduling_values(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    payload["conditions"]["scheduling"]["max_inflight"] = True
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any("scheduling.max_inflight" in error for error in result["errors"])

def test_benchmark_lock_requires_translation_e2e_evaluator_artifact(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    payload["artifacts"] = [
        entry
        for entry in payload["artifacts"]
        if entry.get("id") != "translation_e2e_evaluator"
    ]
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any(
        "required artifact missing: translation_e2e_evaluator" in error
        for error in result["errors"]
    )


def test_benchmark_lock_rejects_translation_e2e_evaluator_mutation(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    artifact = tmp_path / "translation_e2e_benchmark.py"
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any(
        "artifact hash mismatch" in error
        and "translation_e2e_benchmark.py" in error
        for error in result["errors"]
    )
def test_benchmark_lock_rejects_scheduling_artifact_mutation(tmp_path):
    lock_path = _copy_lock_fixture(tmp_path)
    artifact = tmp_path / "vision_scheduling_benchmark.py"
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = validate_benchmark_lock(tmp_path, lock_path)

    assert result["ok"] is False
    assert any("artifact hash mismatch" in error for error in result["errors"])


def test_scheduling_benchmark_conforms_to_locked_contract():
    lock = load_lock(LOCK_PATH)
    condition = lock["conditions"]["scheduling"]
    result = scheduling_benchmark.run_benchmark(**condition["certified_run"])

    validation = validate_scheduling_result(result, condition)

    assert validation == {"ok": True, "errors": []}
