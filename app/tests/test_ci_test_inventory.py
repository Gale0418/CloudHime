"""Regression tests for the single source of truth used by CI test groups."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
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
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "-split '\\s+'" in workflow
    assert "-split '\\\\s+'" not in workflow


def test_ci_uses_explicit_requirements_without_in_process_llama():
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ci_requirements = (ROOT / "requirements-ci.txt").read_text(encoding="utf-8")

    assert "pip install --require-hashes -r requirements-ci-lock-win-amd64-py310.txt" in workflow
    assert "Where-Object { $_.Trim() -and $_.Trim() -ne 'llama-cpp-python' }" not in workflow
    assert "llama-cpp-python" not in ci_requirements

def test_gitignore_covers_cross_tool_probe_roots():
    ignore = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")
    required_patterns = (
        "/.codex-*/",
        "/.h3_*/",
        "/.h3tests/",
        "/_codex_*/",
        "/_pytest_*/",
        "/_tmp_*/",
        "/.tmp/",
        "/tmp*/",
        "/pytest-cache-files-*/",
        "/pytest-runner-writable-*/",
        "/pytest-runtime-*/",
        "/codex_pytest_release_tdd/",
        "/manual-pytest-base/",
        "/.pytest_*/",
        "/.test-temp-*/",
        "/scratch/pytest-*/",
        "/scratch/_pytest_*/",
        "/scratch/flash-pytest-*/",
        "/scratch/jp-rescue-*/",
        "/scratch/_codex_owner_confirm*/",
    )
    for pattern in required_patterns:
        assert pattern in ignore
def test_ci_inventory_includes_release_provenance_contract():
    inventory = _load_inventory()
    assigned = {
        path
        for group in inventory["groups"]
        for path in group["test_files"]
    }
    assert "tests/test_release_provenance.py" in assigned

def test_missioncenter_decisions_reject_c0_control_characters():
    decisions = REPOSITORY_ROOT / "MissionCenter" / "decisions.md"
    content = decisions.read_text(encoding="utf-8")
    unexpected = [
        character
        for character in content
        if ord(character) < 32 and character not in {"\n", "\r", "\t"}
    ]
    assert not unexpected, "MissionCenter decisions contains C0 control characters"


def test_windows_pytest_runner_uses_private_writable_basetemp():
    runner = ROOT / "ci" / "run_pytest.ps1"
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

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


def test_ci_and_ignored_outputs_follow_the_app_layout():
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "defaults:\n  run:\n    working-directory: app" in workflow
    assert (REPOSITORY_ROOT / "app").is_dir()
    assert (REPOSITORY_ROOT / "docs").is_dir()

    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "app/.pytest_cache/"],
        cwd=REPOSITORY_ROOT,
        check=False,
        timeout=10,
    )
    assert ignored.returncode == 0, "pytest cache under app must stay ignored"

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


@pytest.mark.parametrize("fails", [False, True])
def test_windows_isolated_runner_quotes_test_paths_and_preserves_exit_code(tmp_path, fails):
    if os.name != "nt":
        pytest.skip("Windows runner contract")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        pytest.skip("PowerShell is required")
    import sys
    test_file = tmp_path / "probe with spaces.py"
    test_file.write_text(f"def test_probe():\n    assert {not fails!r}\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    completed = subprocess.run(
        [pwsh, "-NoLogo", "-NoProfile", "-File", str(ROOT / "ci/run_pytest.ps1"),
         "-TestFiles", str(test_file), "-IsolateUi"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=40,
    )
    assert completed.returncode == (1 if fails else 0), completed.stdout + completed.stderr


@pytest.mark.parametrize("use_venv", [False, True])
def test_root_launcher_finds_app_from_another_working_directory(tmp_path, use_venv):
    if os.name != "nt":
        pytest.skip("Windows launcher")
    import sys
    repo = tmp_path / "launcher with spaces"
    app = repo / "app"
    app.mkdir(parents=True)
    launcher = repo / "run.bat"
    launcher.write_bytes((REPOSITORY_ROOT / "run.bat").read_bytes())
    receipt = tmp_path / "launch.json"
    (app / "CloudHime.py").write_text(
        "import json,os,sys\nfrom pathlib import Path\n"
        "Path(os.environ['CLOUDHIME_LAUNCH_PROBE']).write_text(json.dumps({'cwd':os.getcwd(),'executable':sys.executable}),encoding='utf-8')\n",
        encoding="utf-8",
    )
    base_python = Path(sys._base_executable)
    if use_venv:
        scripts = app / ".venv/Scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(base_python, scripts / "python.exe")
    env = os.environ.copy()
    env["CLOUDHIME_LAUNCH_PROBE"] = str(receipt)
    env["PYTHONHOME"] = sys.base_prefix
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(base_python.parent) + os.pathsep + str(Path(env["SYSTEMROOT"]) / "System32")
    completed = subprocess.run(
        [str(Path(env["SYSTEMROOT"]) / "System32/cmd.exe"), "/d", "/c", str(launcher)],
        cwd=tmp_path, env=env, input="\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    data = json.loads(receipt.read_text(encoding="utf-8"))
    assert Path(data["cwd"]) == app
    assert (".venv" in Path(data["executable"]).parts) is use_venv


def test_root_example_stays_untracked_and_ignored():
    tracked = subprocess.check_output(
        ["git", "ls-files", "--", "example", "app/example"], cwd=REPOSITORY_ROOT, text=True,
    )
    assert tracked == ""
    for path in ("example/private-probe.png", "app/example/private-probe.png"):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", path], cwd=REPOSITORY_ROOT, timeout=10,
        )
        assert result.returncode == 0
