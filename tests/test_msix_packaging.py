from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET

import pytest


def test_msix_manifest_template_has_desktop_entrypoint_and_logo():
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "packaging" / "Package.appxmanifest.in"
    manifest = ET.parse(manifest_path).getroot()

    ns = {
        "foundation": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
        "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
        "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
    }
    application = manifest.find("foundation:Applications/foundation:Application", ns)
    visual = application.find("uap:VisualElements", ns)
    capability = manifest.find("foundation:Capabilities/rescap:Capability", ns)

    assert application.attrib["Executable"] == "CloudHime.exe"
    assert application.attrib["EntryPoint"] == "Windows.FullTrustApplication"
    assert visual.attrib["Square150x150Logo"] == "__LOGO_PATH__"
    assert visual.attrib["Square44x44Logo"] == "__LOGO_PATH__"
    assert visual.attrib["BackgroundColor"] == "#F4F7FB"
    assert capability is not None
    assert capability.attrib["Name"] == "runFullTrust"


def test_msix_builder_requires_windows_sdk_and_expands_manifest():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "build_msix.ps1").read_text(encoding="utf-8")

    assert "makeappx.exe" in script
    assert "verify_release_dist.ps1" in script
    assert "PreflightOnly" in script
    assert '[ValidateSet("x64")]' in script
    assert "_internal\\assets\\cloudhime_logo.png" in script
    assert "$packagingSucceeded" in script
    assert "Package.appxmanifest.in" in script
    assert "Windows.FullTrustApplication" not in script
    assert "makeappx pack /d" in script
    assert "THIRD_PARTY_NOTICES.md" in (root / "build_exe.bat").read_text(encoding="utf-8")
    assert (root / "assets" / "cloudhime_logo.png").is_file()

    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "AppxManifest.xml" in ci
    assert "runFullTrust" in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\LocalMachine\\TrustedPeople" in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\CurrentUser\\TrustedPeople" not in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\CurrentUser\\Root" not in ci
    assert "Import-Certificate -FilePath $cerPath -CertStoreLocation Cert:\\LocalMachine\\Root" not in ci
    assert '$stores = @("Cert:\\CurrentUser\\My", "Cert:\\LocalMachine\\TrustedPeople")' in ci
    assert "Get-ChildItem -Path $store -ErrorAction Stop" in ci
    assert 'foreach ($store in @("My", "TrustedPeople", "Root"))' not in ci
    assert "CLOUDHIME_CI_CERT_THUMBPRINT" in ci
    assert ci.count("$_.Thumbprint -eq $thumbprint") >= 2
    assert 'Where-Object { $_.Subject -eq "CN=CloudHime CI" }' not in ci
    assert "Remove-Item -Force -ErrorAction Stop" in ci
    assert "Failed to remove CI signing certificate" in ci
    assert "cancel-in-progress: true" in ci
    assert "name: CI" in ci
    assert "fail-fast: false" in ci
    ui_step_start = ci.index("      - name: Run Tests (" + "$" + "{{ matrix.name }})")
    ui_step_end = ci.index("  msix-contract:", ui_step_start)
    ui_step = ci[ui_step_start:ui_step_end]
    assert "if (\'" + "$" + "{{ matrix.name }}\' -eq \'ui\')" in ui_step
    assert "foreach ($testFile in $uiTestFiles)" in ui_step
    assert "shell: pwsh" in ui_step
    assert "Running isolated UI test file" in ui_step
    ui_file_start = ui_step.index("$uiTestFiles = @(")
    ui_file_end = ui_step.index("            )", ui_file_start)
    ui_file_block = ui_step[ui_file_start:ui_file_end]
    for ui_file in ("tests/test_cloudhime_ui_smoke.py", "tests/test_relief_settings.py", "tests/test_settings_window_theme_polish.py", "tests/test_translation_panel_advanced.py"):
        assert ui_file in ui_file_block
    assert "$pytestProcess.WaitForExit(120000)" in ui_step
    assert "if (-not $completed)" in ui_step
    assert "Stop-Process -Id $pytestProcess.Id -Force" in ui_step
    assert 'throw "UI test file timed out after 120 seconds: $testFile"' in ui_step
    assert ui_step.count("if ($pytestProcess.ExitCode -ne 0) { exit $pytestProcess.ExitCode }") == 1
    assert "Build MSIX package" in ci
    assert "Inspect and sign MSIX package" in ci
    assert "Install and uninstall MSIX package" in ci
    assert ci.count("timeout-minutes: 30") == 2
    assert ci.count("timeout-minutes: 10") >= 3

    install_smoke = (root / "packaging" / "test_msix_install.ps1").read_text(encoding="utf-8")
    assert "Add-AppxPackage" in install_smoke
    assert "PSEdition" in install_smoke
    assert "WindowsPowerShell\\v1.0\\powershell.exe" in install_smoke
    assert "-WindowStyle Hidden" in install_smoke
    assert "Start-Process" in install_smoke
    assert "Remove-AppxPackage" in install_smoke
    assert "Refusing to modify an existing package" in install_smoke


def _powershell_executable():
    return shutil.which("pwsh") or shutil.which("powershell")


def _write_release_fixture(powershell, root):
    root_literal = str(root).replace("'", "''")
    runtime_files = (
        "llama-server.exe",
        "llama-server-impl.dll",
        "llama-common.dll",
        "llama.dll",
        "ggml.dll",
        "ggml-base.dll",
        "ggml-cpu-x64.dll",
        "ggml-cuda.dll",
        "mtmd.dll",
        "libomp140.x86_64.dll",
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudart64_12.dll",
    )
    runtime_literal = ", ".join(f'"{filename}"' for filename in runtime_files)
    command = f"""
$root = '{root_literal}'
New-Item -ItemType Directory -Force -Path (Join-Path $root '_internal\\assets'), (Join-Path $root '_internal\\runtime'), (Join-Path $root '_internal\\certifi') | Out-Null
Set-Content -LiteralPath (Join-Path $root 'CloudHime.exe') -Value 'exe' -Encoding ascii
Set-Content -LiteralPath (Join-Path $root '_internal\\certifi\\cacert.pem') -Value 'public CA bundle' -Encoding ascii
Set-Content -LiteralPath (Join-Path $root '_internal\\assets\\cloudhime_logo.png') -Value 'png' -Encoding ascii
foreach ($releaseFile in @('dictionary.json', 'LICENSE', 'THIRD_PARTY_NOTICES.md')) {{
    Set-Content -LiteralPath (Join-Path $root "_internal\\$releaseFile") -Value 'fixture' -Encoding ascii
}}
foreach ($runtimeFile in @({runtime_literal})) {{
    Set-Content -LiteralPath (Join-Path $root "_internal\\runtime\\$runtimeFile") -Value 'runtime' -Encoding ascii
}}
"""
    subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _remove_release_fixture(powershell, root):
    root_literal = str(root).replace("'", "''")
    command = f"if (Test-Path -LiteralPath '{root_literal}') {{ Remove-Item -LiteralPath '{root_literal}' -Recurse -Force }}"
    subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

def test_release_dist_preflight_validates_a_realistic_bundle():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the release preflight script")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "verify_release_dist.ps1"
    temp_root = root / f".tmp-msix-preflight-{uuid.uuid4().hex}"
    fixture = temp_root / "CloudHime"
    try:
        _write_release_fixture(powershell, fixture)
        result = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "ready" in result.stdout.lower()

        invalid_cases = (
            (fixture / "models.gguf", b"must stay in AppData", "AppData"),
            (fixture / ".env.production", b"must stay out of the package", "secrets"),
            (fixture / "dev-signing.pfx", b"must stay in package", "signing material"),
            (fixture / "_internal" / "runtime" / "llama.dll", b"", "required llama/ggml runtime"),
        )
        for invalid_path, payload, expected_message in invalid_cases:
            invalid_path.write_bytes(payload)
            rejected = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert rejected.returncode != 0
            assert expected_message in (rejected.stdout + rejected.stderr)
            if invalid_path.name == "llama.dll":
                invalid_path.write_bytes(b"runtime")
            else:
                invalid_path.unlink()
    finally:
        if temp_root.parent == root and temp_root.name.startswith(".tmp-msix-preflight-"):
            _remove_release_fixture(powershell, temp_root)

def test_real_release_dist_preflight_when_available():
    powershell = _powershell_executable()
    dist = Path(__file__).resolve().parents[1] / "dist" / "CloudHime"
    if not powershell or not dist.is_dir():
        pytest.skip("local PyInstaller dist is not available")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "verify_release_dist.ps1"
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(dist)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
