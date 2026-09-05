from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from ci import corpus_policy as policy

MANGA = "tests/test_manga_repeated_run_evaluator.py::test_public_manga_holdout_manifest_is_evaluator_ready"
TEMPORAL = "tests/test_temporal_holdout_benchmark.py::test_safe_policy_is_lossless_and_near_skip_has_counterexample"


def manifest(root, cases, name="manga_cover_cases.json"):
    directory = root / "benchmarks"
    directory.mkdir(exist_ok=True)
    (directory / name).write_text(json.dumps({"cases": cases}), encoding="utf-8")


def test_unknown_test_never_skips(tmp_path):
    assert policy.missing_files_for_test(tmp_path, "tests/test_security.py::test_key") == ()


def test_only_missing_images_are_optional_and_no_download_occurs(tmp_path):
    manifest(tmp_path, [{"image": "example/missing.jpg"}])
    assert policy.missing_files_for_test(tmp_path, MANGA) == ("example/missing.jpg",)
    (tmp_path / "example").mkdir()
    (tmp_path / "example/missing.jpg").write_bytes(b"corrupt image")
    # Presence does not validate image bytes; the actual evaluator must reject corruption.
    assert policy.missing_files_for_test(tmp_path, MANGA) == ()


def test_missing_manifest_is_an_error_not_a_skip(tmp_path):
    with pytest.raises(FileNotFoundError):
        policy.missing_files_for_test(tmp_path, MANGA)


@pytest.mark.parametrize("image", ["../outside.jpg", "/outside.jpg", "C:\\secret.jpg",
                                    "https://example.org/image.jpg", "", None])
def test_unsafe_or_malformed_paths_are_errors_not_skips(tmp_path, image):
    manifest(tmp_path, [{"image": image}])
    with pytest.raises(ValueError):
        policy.missing_files_for_test(tmp_path, MANGA)


@pytest.mark.parametrize("cases", [[], None, [1], [{}]])
def test_invalid_manifest_is_an_error_not_a_skip(tmp_path, cases):
    manifest(tmp_path, cases)
    with pytest.raises(ValueError):
        policy.missing_files_for_test(tmp_path, MANGA)


def test_synthetic_temporal_case_requires_no_external_image(tmp_path):
    manifest(tmp_path, [{"source": "synthetic://local-content-event"}], "temporal_holdout_cases.json")
    assert policy.missing_files_for_test(tmp_path, TEMPORAL) == ()


def test_manifest_reads_are_bounded(tmp_path, monkeypatch):
    manifest(tmp_path, [{"image": "example/a.jpg"}])
    monkeypatch.setattr(policy, "MAX_MANIFEST_BYTES", 2)
    with pytest.raises(ValueError, match="size limit"):
        policy.missing_files_for_test(tmp_path, MANGA)


def test_skip_and_strict_gate_are_visible_in_actual_pytest(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "tests").mkdir()
    shutil.copytree(root / "ci", tmp_path / "ci", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(root / "tests/conftest.py", tmp_path / "tests/conftest.py")
    manifest(tmp_path, [{"image": "example/missing.jpg"}])
    (tmp_path / "tests/test_manga_repeated_run_evaluator.py").write_text(
        "def test_public_manga_holdout_manifest_is_evaluator_ready():\n    assert False, 'must not run without image'\n", encoding="utf-8")
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    command = [sys.executable, "-m", "pytest", "-q", "-rs", "tests"]
    optional = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30)
    assert optional.returncode == 0, optional.stdout + optional.stderr
    assert "1 skipped" in optional.stdout and "not quality evidence" in optional.stdout
    strict = subprocess.run([*command, "--require-external-corpora"], cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30)
    assert strict.returncode == 4, strict.stdout + strict.stderr
    assert "Required external corpus is missing" in strict.stderr


def test_core_only_pytest_does_not_import_qt(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "tests").mkdir()
    shutil.copytree(root / "ci", tmp_path / "ci", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(root / "tests/conftest.py", tmp_path / "tests/conftest.py")
    (tmp_path / "tests/test_core_probe.py").write_text(
        "import sys\ndef test_no_gui():\n    assert 'cloudhime_ui' not in sys.modules\n    assert 'PySide6.QtWidgets' not in sys.modules\n", encoding="utf-8")
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=tmp_path,
                            env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
