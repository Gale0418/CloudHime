import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import yaml
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
    assert visual.attrib["Square150x150Logo"] == "__LOGO_150_PATH__"
    assert visual.attrib["Square44x44Logo"] == "__LOGO_44_PATH__"
    assert "__LOGO_50_PATH__" in manifest_path.read_text(encoding="utf-8")
    assert visual.attrib["BackgroundColor"] == "#F4F7FB"
    assert capability is not None
    assert capability.attrib["Name"] == "runFullTrust"


def test_msix_builder_prefers_x64_makeappx_for_large_payloads():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "build_msix.ps1").read_text(encoding="utf-8")

    assert "x64[\\\\/]makeappx" in script
    assert "Where-Object" in script

def test_ci_msix_signing_prefers_x64_signtool():
    root = Path(__file__).resolve().parents[1]
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "x64[\\\\/]signtool" in ci

def test_msix_builder_requires_windows_sdk_and_expands_manifest():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "build_msix.ps1").read_text(encoding="utf-8")

    assert "makeappx.exe" in script
    assert "verify_release_dist.ps1" in script
    assert "PreflightOnly" in script
    assert '[ValidateSet("x64")]' in script
    assert "_internal\\assets\\cloudhime_logo_44.png" in script
    assert "_internal\\assets\\cloudhime_logo_50.png" in script
    assert "_internal\\assets\\cloudhime_logo_150.png" in script
    assert "__LOGO_44_PATH__" in script
    assert "__LOGO_50_PATH__" in script
    assert "__LOGO_150_PATH__" in script
    assert "$packagingSucceeded" in script
    assert "Package.appxmanifest.in" in script
    assert "Windows.FullTrustApplication" not in script
    assert "makeappx pack /d" in script
    build_exe = (root / "build_exe.bat").read_text(encoding="utf-8")
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")
    assert "THIRD_PARTY_NOTICES.md" in spec
    assert "manifest='packaging\\\\CloudHime.exe.manifest'" in spec
    assert "CloudHime.spec" in build_exe
    exe_manifest = (root / "packaging" / "CloudHime.exe.manifest").read_text(encoding="utf-8")
    assert "<dpiAware>true/pm</dpiAware>" in exe_manifest
    assert "<dpiAwareness>PerMonitorV2</dpiAwareness>" in exe_manifest
    assert (root / "assets" / "cloudhime_logo.png").is_file()
    for logo_size in ("44", "50", "150"):
        assert (root / "assets" / f"cloudhime_logo_{logo_size}.png").is_file()

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
    assert "test-inventory:" in ci
    assert "ci/test_groups.json" in ci
    assert "fromJSON(needs.test-inventory.outputs.matrix)" in ci
    ui_step_start = ci.index("      - name: Run Tests (" + "$" + "{{ matrix.name }})")
    ui_step_end = ci.index("  msix-contract:", ui_step_start)
    ui_step = ci[ui_step_start:ui_step_end]
    assert "if (\'" + "$" + "{{ matrix.name }}\' -eq \'ui\')" in ui_step
    assert "foreach ($testFile in $testFiles)" in ui_step
    assert r"-split '\s+'" in ui_step
    assert "shell: pwsh" in ui_step
    assert "Running isolated UI test file" in ui_step
    assert "$pytestProcess.WaitForExit(120000)" in ui_step
    assert "if (-not $completed)" in ui_step
    assert "Stop-Process -Id $pytestProcess.Id -Force" in ui_step
    assert 'throw "UI test file timed out after 120 seconds: $testFile"' in ui_step
    assert ui_step.count("if ($pytestProcess.ExitCode -ne 0) { exit $pytestProcess.ExitCode }") == 1
    msix_job = ci[ci.index("  msix-contract:"):]
    assert "uses: actions/setup-python@v5" in msix_job
    assert "python-version: '3.10'" in msix_job
    assert "Build MSIX package" in ci
    assert "Inspect and sign MSIX package" in ci
    assert "Install and uninstall MSIX package" in ci
    assert "runtime-manifest.json" in ci
    assert "ConvertTo-Json" in ci
    assert "Get-FileHash" in ci
    assert "source_commit" in ci
    assert ci.count("timeout-minutes: 30") >= 2
    assert ci.count("timeout-minutes: 10") >= 3

    install_smoke = (root / "packaging" / "test_msix_install.ps1").read_text(encoding="utf-8")
    assert "Add-AppxPackage" in install_smoke
    assert "PSEdition" in install_smoke
    assert "WindowsPowerShell\\v1.0\\powershell.exe" in install_smoke
    assert "-WindowStyle Hidden" in install_smoke
    assert "Start-Process" in install_smoke
    assert "Remove-AppxPackage" in install_smoke
    assert "msix_install_helpers.ps1" in install_smoke
    assert "Remove-AppxPackageForCleanup" in install_smoke
    assert (root / "packaging" / "msix_install_helpers.ps1").is_file()
    assert "Refusing to modify an existing package" in install_smoke



def test_msix_launch_liveness_rejects_exits_and_accepts_alive_processes():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the MSIX launch liveness test")

    script = Path(__file__).resolve().parents[1] / "packaging" / "test_msix_install.ps1"
    script_literal = str(script).replace("'", "''")
    command = f"""
$ErrorActionPreference = "Stop"
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{script_literal}', [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) {{ throw "Install smoke script did not parse." }}
$function = $ast.Find({{ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq "Assert-ProcessLaunchLiveness" }}, $true)
if ($null -eq $function) {{ throw "Launch liveness helper was not found." }}
. ([scriptblock]::Create($function.Extent.Text))
$cases = @(
    @{{ Process = [pscustomobject]@{{ HasExited = $true; ExitCode = 0 }}; Expected = "exited before launch liveness window" }},
    @{{ Process = [pscustomobject]@{{ HasExited = $true; ExitCode = 23 }}; Expected = "code 23" }},
    @{{ Process = [pscustomobject]@{{ HasExited = $false; ExitCode = $null }}; Expected = $null }}
)
foreach ($case in $cases) {{
    try {{
        Assert-ProcessLaunchLiveness -Process $case.Process
        if ($null -ne $case.Expected) {{ throw "Exited process was accepted." }}
    }} catch {{
        if ($null -eq $case.Expected -or $_.Exception.Message -notmatch [regex]::Escape($case.Expected)) {{ throw }}
    }}
}}
"""
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr



def test_ci_workflow_parses_as_yaml():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))

    assert workflow["jobs"]["msix-contract"]

def test_ci_msix_fixture_uses_a_sleeper_executable_with_liveness_margin():
    root = Path(__file__).resolve().parents[1]
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    fixture = ci[ci.index("      - name: Prepare MSIX contract fixture"):ci.index("      - name: Build MSIX package")]
    install = ci[ci.index("      - name: Install and uninstall MSIX package"):]

    assert "cmd.exe" not in fixture
    assert "$launchWaitSeconds = 3" in fixture
    assert "$sleeperMilliseconds = ($launchWaitSeconds + 5) * 1000" in fixture
    assert r"Microsoft.NET\Framework64\v4.0.30319\csc.exe" in fixture
    assert '/target:winexe' in fixture
    assert '& $csc /nologo /target:winexe /out:$sleeperPath $sleeperSourcePath' in fixture
    assert "Thread.Sleep($sleeperMilliseconds);" in fixture
    assert 'Remove-Item -LiteralPath $sleeperSourcePath -Force' in fixture
    assert "-LaunchWaitSeconds 3" in install


def test_msix_cleanup_helper_retries_and_selects_newest_package():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the MSIX cleanup helper test")

    helper = Path(__file__).resolve().parents[1] / "packaging" / "msix_install_helpers.ps1"
    helper_literal = str(helper).replace("'", "''")
    command = f"""
$ErrorActionPreference = "Stop"
. '{helper_literal}'
$script:queryCount = 0
$script:removedPackage = $null
function global:Get-AppxPackage {{
    [CmdletBinding()]
    param([string]$Name)
    $script:queryCount += 1
    if ($script:queryCount -eq 1) {{ return @() }}
    return @(
        [pscustomobject]@{{ Version = [version]"0.1.0.0"; PackageFullName = "CloudHime_0.1.0.0_x64__old" }},
        [pscustomobject]@{{ Version = [version]"0.2.0.0"; PackageFullName = "CloudHime_0.2.0.0_x64__new" }}
    )
}}
function global:Remove-AppxPackage {{
    [CmdletBinding()]
    param([string]$Package)
    $script:removedPackage = $Package
}}
$package = Remove-AppxPackageForCleanup -InstalledPackage $null -IdentityName "CloudHime" -MaxAttempts 3
if ($package.PackageFullName -ne "CloudHime_0.2.0.0_x64__new") {{ throw "Newest package was not selected." }}
if ($script:removedPackage -ne "CloudHime_0.2.0.0_x64__new") {{ throw "Selected package was not removed." }}
if ($script:queryCount -ne 2) {{ throw "Expected one retry, got $script:queryCount queries." }}
"""
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr

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
    _write_runtime_manifest(root / "_internal" / "runtime")
    source_root = Path(__file__).resolve().parents[1]
    shutil.copyfile(
        source_root / "THIRD_PARTY_NOTICES.md",
        root / "_internal" / "THIRD_PARTY_NOTICES.md",
    )
    for logo_size in ("44", "50", "150"):
        shutil.copyfile(
            source_root / "assets" / f"cloudhime_logo_{logo_size}.png",
            root / "_internal" / "assets" / f"cloudhime_logo_{logo_size}.png",
        )
    _write_release_provenance(root)

def _write_release_provenance(root):
    source_root = Path(__file__).resolve().parents[1]
    evidence_root = root.parent / "provenance-source"
    evidence_root.mkdir(parents=True, exist_ok=True)
    report = evidence_root / "report.json"
    requirements = evidence_root / "requirements.txt"
    lock = evidence_root / "requirements-lock-win-amd64-py310.txt"
    sbom = evidence_root / "sbom.cdx.json"
    report.write_text(json.dumps({"version": "1", "pip_version": "26.0", "environment": {"implementation_name": "cpython", "python_version": "3.10.14", "sys_platform": "win32", "platform_machine": "AMD64"}, "install": [{"download_info": {"url": "https://files.example.test/alpha-pkg-1.0.0-py3-none-any.whl", "archive_info": {"hashes": {"sha256": "a" * 64}}}, "requested": True, "metadata": {"name": "alpha-pkg", "version": "1.0.0", "license_expression": "MIT", "requires_dist": []}}]}), encoding="utf-8")
    requirements.write_text("alpha-pkg==1.0.0\n", encoding="utf-8")
    lock.write_text("alpha-pkg==1.0.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(source_root / "packaging" / "dependency_contract.py"), "validate", "--report", str(report), "--requirements", str(lock), "--direct-requirements", str(requirements), "--lock", str(lock), "--sbom-output", str(sbom)], check=True, capture_output=True, text=True, encoding="utf-8")
    subprocess.run([sys.executable, str(source_root / "packaging" / "release_provenance.py"), "stage", "--report", str(report), "--requirements", str(requirements), "--lock", str(lock), "--sbom", str(sbom), "--output", str(root / "_internal" / "provenance")], check=True, capture_output=True, text=True, encoding="utf-8")

def _write_runtime_manifest(runtime_root):
    entries = []
    for path in sorted(runtime_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(runtime_root).as_posix()
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "schema_version": 1,
        "runtime": "llama-server",
        "server": {"path": "llama-server.exe", "version": "fixture"},
        "build": {
            "source_commit": "fixture",
            "backend": "cuda",
            "architecture": "x64",
        },
        "files": entries,
    }
    (runtime_root / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
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

        logo_path = fixture / "_internal" / "assets" / "cloudhime_logo_44.png"
        valid_logo = logo_path.read_bytes()
        for invalid_logo in (valid_logo[:20], valid_logo[:-1] + bytes([valid_logo[-1] ^ 1])):
            logo_path.write_bytes(invalid_logo)
            rejected_logo = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert rejected_logo.returncode != 0
            assert "44x44" in (rejected_logo.stdout + rejected_logo.stderr)
            logo_path.write_bytes(valid_logo)

        invalid_cases = (
            (fixture / "models.gguf", b"must stay in AppData", "AppData"),
            (fixture / ".env.production", b"must stay out of the package", "secrets"),
            (fixture / "dev-signing.pfx", b"must stay in package", "signing material"),
            (fixture / "_internal" / "_llama_cpp.cp310-win_amd64.pyd", b"binding", "in-process llama"),
            (fixture / "_internal" / "llama_cpp" / "__init__.py", b"binding", "in-process llama"),
            (fixture / "_internal" / "llama.dll", b"duplicate", "outside the runtime directory"),
            (fixture / "_internal" / "ggml-extra.dll", b"duplicate", "outside the runtime directory"),
            (fixture / "_internal" / "cudart64_12.dll", b"duplicate", "outside the runtime directory"),
            (fixture / "_internal" / "runtime" / "llama.dll", b"", "required llama/ggml runtime"),
            (fixture / "_internal" / "runtime" / "ggml.dll", b"tampered", "hash or size mismatch"),
            (fixture / "_internal" / "runtime" / "unexpected.dll", b"unexpected", "runtime manifest"),
        )
        for invalid_path, payload, expected_message in invalid_cases:
            original_payload = invalid_path.read_bytes() if invalid_path.is_file() else None
            invalid_path.parent.mkdir(parents=True, exist_ok=True)
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
            if original_payload is not None:
                invalid_path.write_bytes(original_payload)
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
    manifest_candidates = (
        dist / "runtime" / "runtime-manifest.json",
        dist / "_internal" / "runtime" / "runtime-manifest.json",
    )
    if not any(path.is_file() for path in manifest_candidates):
        pytest.skip("local PyInstaller dist predates the runtime manifest; clean rebuild required")

    provenance_candidates = (
        dist / "_internal" / "provenance" / "release-provenance.json",
    )
    if not any(path.is_file() for path in provenance_candidates):
        pytest.skip("local PyInstaller dist predates release provenance; clean rebuild required")

    script = root / "packaging" / "verify_release_dist.ps1"
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(dist)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr

def test_release_dist_preflight_rejects_incomplete_third_party_notices():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the release preflight script")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "verify_release_dist.ps1"
    temp_root = root / f".tmp-msix-notices-{uuid.uuid4().hex}"
    fixture = temp_root / "CloudHime"
    try:
        _write_release_fixture(powershell, fixture)
        notice_path = fixture / "_internal" / "THIRD_PARTY_NOTICES.md"
        notice_path.write_text("## Knowledge research providers\n- ddgs\n", encoding="utf-8")
        result = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert result.returncode != 0
        assert "third-party notices" in (result.stdout + result.stderr).lower()
    finally:
        if temp_root.parent == root and temp_root.name.startswith(".tmp-msix-notices-"):
            _remove_release_fixture(powershell, temp_root)


def test_release_preflight_requires_self_contained_dependency_provenance_and_ci_unpacks_it():
    root = Path(__file__).resolve().parents[1]
    verifier = (root / "packaging" / "verify_release_dist.ps1").read_text(encoding="utf-8")
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "release_provenance.py" in verifier
    assert "_internal\\provenance" in verifier
    assert "release_provenance.py stage" in ci
    assert "release_provenance.py verify" in ci
    assert "_internal\\provenance\\release-provenance.json" in ci

def test_release_preflight_rejects_missing_or_tampered_dependency_provenance():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the release preflight script")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "verify_release_dist.ps1"
    temp_root = root / f".tmp-provenance-preflight-{uuid.uuid4().hex}"
    fixture = temp_root / "CloudHime"
    try:
        _write_release_fixture(powershell, fixture)
        evidence = fixture / "_internal" / "provenance" / "requirements.txt"
        original = evidence.read_bytes()
        for payload in (None, b"tampered\n"):
            if payload is None:
                evidence.unlink()
            else:
                evidence.write_bytes(payload)
            result = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert result.returncode != 0
            assert "provenance" in (result.stdout + result.stderr).lower()
            evidence.write_bytes(original)
    finally:
        if temp_root.parent == root and temp_root.name.startswith(".tmp-provenance-preflight-"):
            _remove_release_fixture(powershell, temp_root)
