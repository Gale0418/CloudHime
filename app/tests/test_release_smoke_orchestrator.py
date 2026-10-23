from __future__ import annotations

from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _powershell_executable() -> str | None:
    candidates = (
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
        Path(r"C:\Program Files\PowerShell\7-preview\pwsh.exe"),
        Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
    )
    return next((str(path) for path in candidates if path.is_file()), None)


def test_release_orchestrator_has_fail_closed_stage_order() -> None:
    script_path = ROOT / "packaging" / "test_release_smoke.ps1"
    assert script_path.is_file()
    script = script_path.read_text(encoding="utf-8")

    assert "verify_release_dist.ps1" in script
    assert "release_functional_smoke.py" in script
    assert "test_clean_machine.ps1" in script
    assert "--validate-only" in script
    assert "--runtime-dir" in script
    assert "--model" in script
    assert "--projector" in script
    assert "--image" in script
    assert "$RequireGpu" in script
    assert "$ForceCpu" in script
    assert "$PythonPath" in script
    assert "UserInteractive" in script
    assert "LASTEXITCODE" in script
    assert "{ 20; break" in script
    assert "{ 30; break" in script
    assert "{ 40; break" in script
    assert script.index("release dist preflight") < script.index("functional smoke input validation")
    assert script.index("functional smoke input validation") < script.index("environment-isolated packaged launch")
    assert script.index("environment-isolated packaged launch") < script.index("functional vision smoke")
    assert "Stop-Process" not in script


def test_release_orchestrator_is_valid_powershell() -> None:
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the orchestrator parser test")

    script_path = ROOT / "packaging" / "test_release_smoke.ps1"
    literal = str(script_path).replace("'", "''")
    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-Command",
            (
                "$tokens = $null; $errors = $null; "
                f"[System.Management.Automation.Language.Parser]::ParseFile('{literal}', [ref]$tokens, [ref]$errors) | Out-Null; "
                "if ($errors.Count) { $errors | ForEach-Object { $_.Message }; exit 1 }"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_orchestrator_runs_functional_smoke_inside_packaged_exe():
    script = (ROOT / "packaging" / "test_release_smoke.ps1").read_text(encoding="utf-8")

    assert "-FunctionalSmoke" in script
    assert "-AdditionalEnvironmentVariables" in script
    assert "CLOUDHIME_PACKAGED_FUNCTIONAL_SMOKE" in script
    assert "CLOUDHIME_PACKAGED_SMOKE_RESULT_PATH" in script
    assert "packaged functional smoke result" in script
    assert '$PythonPath @smokeArgs "--json"' not in script
