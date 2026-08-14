"""Regression tests for the single source of truth used by CI test groups."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "ci" / "test_groups.json"


def _load_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _repository_test_files() -> set[str]:
    return {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests").glob("test_*.py")
    }


def test_ci_inventory_assigns_every_test_file_exactly_once():
    inventory = _load_inventory()
    groups = inventory.get("groups")
    assert isinstance(groups, list) and groups

    group_names = [group.get("name") for group in groups]
    assert all(isinstance(name, str) and name for name in group_names)
    assert len(group_names) == len(set(group_names))

    assignments: list[str] = []
    for group in groups:
        files = group.get("test_files")
        assert isinstance(files, list), group.get("name")
        assert all(isinstance(path, str) for path in files), group.get("name")
        assignments.extend(files)

    assert len(assignments) == len(set(assignments)), "a test file is assigned more than once"
    assert set(assignments) == _repository_test_files()


def test_ci_inventory_points_only_to_existing_test_files():
    inventory = _load_inventory()
    assigned = {
        path
        for group in inventory["groups"]
        for path in group["test_files"]
    }
    assert all((ROOT / path).is_file() for path in assigned)
    assert all(path.startswith("tests/test_") and path.endswith(".py") for path in assigned)

def test_ci_matrix_runner_splits_paths_on_whitespace():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "-split '\\s+'" in workflow
    assert "-split '\\\\s+'" not in workflow


def test_ci_uses_explicit_requirements_without_in_process_llama():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ci_requirements = (ROOT / "requirements-ci.txt").read_text(encoding="utf-8")

    assert "pip install --require-hashes -r requirements-ci-lock-win-amd64-py310.txt" in workflow
    assert "Where-Object { $_.Trim() -and $_.Trim() -ne 'llama-cpp-python' }" not in workflow
    assert "llama-cpp-python" not in ci_requirements

def test_ci_inventory_includes_release_provenance_contract():
    inventory = _load_inventory()
    assigned = {
        path
        for group in inventory["groups"]
        for path in group["test_files"]
    }
    assert "tests/test_release_provenance.py" in assigned

def test_missioncenter_decisions_reject_c0_control_characters():
    decisions = ROOT / "MissionCenter" / "decisions.md"
    content = decisions.read_text(encoding="utf-8")
    unexpected = [
        character
        for character in content
        if ord(character) < 32 and character not in {"\n", "\r", "\t"}
    ]
    assert not unexpected, "MissionCenter decisions contains C0 control characters"


def test_windows_pytest_runner_uses_private_writable_basetemp():
    runner = ROOT / "ci" / "run_pytest.ps1"
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert runner.is_file()
    runner_content = runner.read_text(encoding="utf-8")
    assert "RUNNER_TEMP" in runner_content
    assert "GetTempPath" in runner_content
    assert "basetemp" in runner_content
    assert "WriteAllText" in runner_content
    assert "Remove-Item -LiteralPath" in runner_content
    assert "2>&1 | Out-Host" in runner_content
    assert "$pytestExitCode = $LASTEXITCODE" in runner_content
    assert "ci\\run_pytest.ps1" in workflow
    assert "-TestFiles $testFiles" in workflow
    assert "-IsolateUi" in workflow

def test_windows_pytest_runner_preserves_space_in_runner_temp(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows runner contract")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        pytest.skip("PowerShell is required")

    runner = ROOT / "ci" / "run_pytest.ps1"
    runner_temp = tmp_path / "runner temp"
    env = os.environ.copy()
    env["RUNNER_TEMP"] = str(runner_temp)
    completed = subprocess.run(
        [
            pwsh,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(runner),
            "-TestFiles",
            "ci/pytest_runner_probe.py",
            "-IsolateUi",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
