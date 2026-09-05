from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow():
    # BaseLoader preserves the YAML 1.2 Actions key `on` (rather than bool True).
    return yaml.load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_dependency_contract_uses_the_populated_venv_for_all_reports():
    job = workflow()["jobs"]["dependency-contract"]
    step = next(s for s in job["steps"] if s.get("name") == "Resolve dependencies in an isolated environment")
    commands = [line.strip() for line in step["run"].splitlines() if "packaging\\dependency_contract.py" in line]
    assert len(commands) == 4
    assert all(line.startswith("& $venvPython ") for line in commands)
    assert "CI venv creation failed." in step["run"]


def test_msix_installs_only_hash_pinned_contract_tooling_before_fixture():
    steps = workflow()["jobs"]["msix-contract"]["steps"]
    install = next(i for i, step in enumerate(steps) if step.get("name") == "Install minimal contract tooling")
    fixture = next(i for i, step in enumerate(steps) if step.get("name") == "Prepare MSIX contract fixture")
    assert install < fixture
    assert "python -m pip install --require-hashes -r ci/requirements-contract.txt" in steps[install]["run"]
    lines = [line for line in (ROOT / "ci/requirements-contract.txt").read_text().splitlines() if line and not line.startswith("#")]
    assert len(lines) == 1
    assert lines[0] == "packaging==26.3 --hash=sha256:d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"


def test_existing_workflow_triggers_and_manual_release_gates_are_preserved():
    config = workflow()
    assert set(config["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert "workflow_dispatch" in config["jobs"]["real-release-build"]["if"]
    assert "workflow_dispatch" in config["jobs"]["real-release-smoke"]["if"]
    assert config["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("name", ["benchmarks/translation_e2e_cases.json", "benchmarks/temporal_holdout_cases.json",
                                  "vision_scheduling_benchmark.py", "translation_e2e_benchmark.py"])
def test_git_checkout_preserves_locked_bytes_with_autocrlf_enabled(tmp_path, name):
    git = shutil.which("git")
    if git is None:
        pytest.skip("Git executable is required to verify checkout attributes")
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True, timeout=10)
    subprocess.run([git, "-C", str(tmp_path), "config", "core.autocrlf", "true"], check=True, timeout=10)
    shutil.copy2(ROOT / ".gitattributes", tmp_path / ".gitattributes")
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    original = b"first\nsecond\n"
    target.write_bytes(original)
    subprocess.run([git, "-C", str(tmp_path), "add", "."], check=True, capture_output=True, timeout=10)
    target.unlink()
    subprocess.run([git, "-C", str(tmp_path), "checkout-index", "-f", "--all"], check=True, timeout=10)
    assert target.read_bytes() == original


def test_new_regressions_belong_to_the_ci_inventory():
    inventory = json.loads((ROOT / "ci/test_groups.json").read_text())
    declared = [name for group in inventory["groups"] for name in group["test_files"]]
    assert len(declared) == len(set(declared))
    for name in ["test_corpus_policy.py", "test_frame_metrics.py", "test_native_frame_metrics.py", "test_stabilization_contracts.py"]:
        assert declared.count("tests/" + name) == 1


def test_rust_version_and_offline_commands_are_explicit():
    text = (ROOT / "native/rust-toolchain.toml").read_text()
    assert 'channel = "1.98.1"' in text
    manifest = (ROOT / "native/Cargo.toml").read_text()
    assert 'rust-version = "1.98.1"' in manifest
    assert "[dependencies]" not in manifest
    script = (ROOT / "native/verify.py").read_text()
    assert '[rustup, "run", "1.98.1"]' in script
    assert '"--offline"' in script and '"--locked"' in script
