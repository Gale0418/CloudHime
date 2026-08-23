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

def test_ci_msix_contract_runs_environment_isolated_launch_smoke():
    root = Path(__file__).resolve().parents[1]
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "packaging/test_clean_machine.ps1" in ci
    assert "Environment-isolated release executable smoke" in ci
    assert "Structural launch smoke only" in ci
    assert "packaging/release_functional_smoke.py" in ci
    assert "-ExecutablePath $executable" in ci
    assert "-LaunchWaitSeconds 5" in ci
    assert ci.index("Environment-isolated release executable smoke") > ci.index("Prepare MSIX contract fixture")
    assert ci.index("Environment-isolated release executable smoke") < ci.index("Build MSIX package")

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
    assert "-TestFiles $testFiles" in ui_step
    assert "-IsolateUi" in ui_step
    assert r"-split '\s+'" in ui_step
    assert "shell: pwsh" in ui_step
    runner = (root / "ci" / "run_pytest.ps1").read_text(encoding="utf-8")
    assert "Running isolated UI test file" in runner
    assert "WaitForExit($TimeoutSeconds * 1000)" in runner
    assert "Stop-Process -Id $process.Id -Force" in runner
    assert 'throw "UI test file timed out after $TimeoutSeconds seconds' in runner
    assert "--basetemp" in runner
    msix_job = ci[ci.index("  msix-contract:"):]
    assert "uses: actions/setup-python@v5" in msix_job
    assert "python-version: '3.10'" in msix_job
    assert "Build MSIX package" in ci
    assert "Inspect and sign MSIX package" in ci
    assert "Install and uninstall MSIX package" in ci
    assert "runtime-manifest.json" in ci
    assert "runtimeManifest.build.architecture" in ci
    assert "ConvertTo-Json" in ci
    assert "Get-FileHash" in ci
    assert "source_commit" in ci
    assert ci.count("timeout-minutes: 30") >= 2
    assert ci.count("timeout-minutes: 10") >= 3

    install_smoke = (root / "packaging" / "test_msix_install.ps1").read_text(encoding="utf-8")
    assert "Add-AppxPackage" in install_smoke
    assert "PSEdition" in install_smoke
    assert "WindowsPowerShell\\v1.0\\powershell.exe" in install_smoke
    assert '[string]$ApplicationId = "CloudHime"' in install_smoke
    assert '"-ApplicationId"' in install_smoke
    assert "$ApplicationId" in install_smoke
    assert "Start-Process" not in install_smoke
    assert "Activate-AppxApplication" in install_smoke
    assert "$processId" in install_smoke
    assert "Stop-Process -Id $processId" in install_smoke
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



def test_msix_activation_helper_uses_aumid_and_returns_the_activated_process():
    root = Path(__file__).resolve().parents[1]
    helper = (root / "packaging" / "msix_install_helpers.ps1").read_text(encoding="utf-8")

    assert "function Activate-AppxApplication" in helper
    assert "IApplicationActivationManager" in helper
    assert "2e941141-7f97-4756-ba1d-9decde894a3d" in helper
    assert "45BA127D-10A8-46EA-8AB7-56EA9078943C" in helper
    assert "ActivateApplication" in helper
    assert "public static class ApplicationActivationManagerLauncher" in helper
    assert "public static uint ActivateApplication(string appUserModelId)" in helper
    assert "(IApplicationActivationManager)Activator.CreateInstance(typeof(ApplicationActivationManager))" in helper
    assert "Marshal.ReleaseComObject(activationManager)" in helper
    assert "[AppxSmoke.IApplicationActivationManager](New-Object AppxSmoke.ApplicationActivationManager)" not in helper
    assert '"$packageFamilyName!$ApplicationId"' in helper
    assert "[string]::IsNullOrWhiteSpace($packageFamilyName)" in helper
    assert "[string]::IsNullOrWhiteSpace($ApplicationId)" in helper
    assert "ProcessId = [int]$processId" in helper
    assert "Process = $process" in helper


def test_ci_workflow_parses_as_yaml():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))

    assert workflow["jobs"]["msix-contract"]

def test_ci_msix_fixture_uses_an_environment_probe_with_liveness_margin():
    root = Path(__file__).resolve().parents[1]
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    fixture = ci[ci.index("      - name: Prepare MSIX contract fixture"):ci.index("      - name: Build MSIX package")]
    install = ci[ci.index("      - name: Install and uninstall MSIX package"):]

    assert "cmd.exe" not in fixture
    assert "$launchWaitSeconds = 5" in fixture
    assert "$probeMilliseconds = ($launchWaitSeconds + 5) * 1000" in fixture
    assert r"Microsoft.NET\Framework64\v4.0.30319\csc.exe" in fixture
    assert '/target:winexe' in fixture
    assert '& $csc /nologo /target:winexe /out:$probePath $probeSourcePath' in fixture
    assert "Environment.GetEnvironmentVariable" in fixture
    for sandbox_marker in (
        'Environment.GetEnvironmentVariable("LOCALAPPDATA")',
        'Environment.GetEnvironmentVariable("APPDATA")',
        'Environment.GetEnvironmentVariable("TEMP")',
        'Environment.GetEnvironmentVariable("TMP")',
        'cloudhime-clean-machine-',
        'return 15;',
        'return 16;',
    ):
        assert sandbox_marker in fixture
    for guard in (
        'if (String.IsNullOrWhiteSpace(systemRoot)) return 11;',
        'if (Environment.GetEnvironmentVariable("WINDIR") != systemRoot) return 12;',
        'if (Environment.GetEnvironmentVariable("PATH") != expectedPath) return 13;',
    ):
        assert guard in fixture
    for forbidden in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX", "OLLAMA_HOST"):
        assert forbidden in fixture
    assert "Thread.Sleep(__PROBE_MS__);" in fixture
    assert '$probeSource = $probeSource.Replace("__PROBE_MS__", $probeMilliseconds.ToString())' in fixture
    assert 'Remove-Item -LiteralPath $probeSourcePath -Force' in fixture
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
        manifest_path = fixture / "_internal" / "runtime" / "runtime-manifest.json"
        valid_manifest = manifest_path.read_text(encoding="utf-8")
        manifest_path.write_text(valid_manifest.replace('"architecture": "x64"', '"architecture": "arm64"'), encoding="utf-8")
        rejected_architecture = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert rejected_architecture.returncode != 0
        assert "architecture" in (rejected_architecture.stdout + rejected_architecture.stderr).lower()
        manifest_path.write_text(valid_manifest, encoding="utf-8")

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
            (fixture / "_internal" / "llama-server.exe", b"duplicate", "outside the runtime directory"),
            (fixture / "_internal" / "ggml-extra.dll", b"duplicate", "outside the runtime directory"),
            (fixture / "_internal" / "cudart64_12.dll", b"duplicate", "outside the runtime directory"),
            (fixture / "_internal" / "cudart64_11.dll", b"duplicate CUDA runtime", "outside the runtime directory"),
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

def test_release_dist_preflight_unpacked_msix_mode_is_narrow_and_validated():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the release preflight script")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "verify_release_dist.ps1"
    temp_root = root / f".tmp-msix-unpacked-{uuid.uuid4().hex}"
    fixture = temp_root / "CloudHime"
    manifest = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
  <Identity Name="CloudHime" Publisher="CN=CloudHime CI" ProcessorArchitecture="x64" Version="0.1.0.0" />
</Package>
"""
    expected_args = [
        powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture),
        "-UnpackedMsix", "-ExpectedIdentityName", "CloudHime",
        "-ExpectedPublisher", "CN=CloudHime CI", "-ExpectedArchitecture", "x64",
    ]
    try:
        _write_release_fixture(powershell, fixture)
        (fixture / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
        (fixture / "AppxBlockMap.xml").write_text("<BlockMap />\n", encoding="utf-8")

        default_result = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert default_result.returncode != 0
        assert "generated msix files" in (default_result.stdout + default_result.stderr).lower()

        unpacked_result = subprocess.run(
            expected_args, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert unpacked_result.returncode == 0, unpacked_result.stdout + unpacked_result.stderr

        custom_manifest = manifest.replace('Name="CloudHime"', 'Name="CloudHime.Store"').replace(
            'Publisher="CN=CloudHime CI"', 'Publisher="CN=CloudHime Store"',
        )
        (fixture / "AppxManifest.xml").write_text(custom_manifest, encoding="utf-8")
        custom_result = subprocess.run(
            [
                *expected_args[:-6],
                "-ExpectedIdentityName", "CloudHime.Store",
                "-ExpectedPublisher", "CN=CloudHime Store",
                "-ExpectedArchitecture", "x64",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert custom_result.returncode == 0, custom_result.stdout + custom_result.stderr
        (fixture / "AppxManifest.xml").write_text(manifest, encoding="utf-8")

        invalid_cases = (
            (fixture / "nested" / "AppxManifest.xml", manifest, expected_args, "generated msix files"),
            (fixture / "extra.msix", "package", expected_args, "generated msix files"),
            (fixture / "extra.appx", "package", expected_args, "generated msix files"),
            (fixture / "release-signing.pfx", "secret", expected_args, "signing material"),
            (
                fixture / "AppxManifest.xml",
                manifest.replace('Name="CloudHime"', 'Name="Unexpected"'),
                expected_args,
                "unexpected identity name. expected 'cloudhime'.",
            ),
            (
                fixture / "AppxManifest.xml",
                manifest.replace('Publisher="CN=CloudHime CI"', 'Publisher="CN=Unexpected Publisher"'),
                expected_args,
                "unexpected publisher. expected 'cn=cloudhime ci'.",
            ),
            (
                fixture / "AppxManifest.xml",
                manifest.replace('ProcessorArchitecture="x64"', 'ProcessorArchitecture="arm64"'),
                expected_args,
                "unexpected processor architecture. expected 'x64'.",
            ),
        )
        for invalid_path, payload, verifier_args, expected_message in invalid_cases:
            original_payload = invalid_path.read_text(encoding="utf-8") if invalid_path.is_file() else None
            invalid_path.parent.mkdir(parents=True, exist_ok=True)
            invalid_path.write_text(payload, encoding="utf-8")
            rejected = subprocess.run(
                verifier_args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            assert rejected.returncode != 0
            assert expected_message in (rejected.stdout + rejected.stderr).lower()
            if original_payload is None:
                invalid_path.unlink()
            else:
                invalid_path.write_text(original_payload, encoding="utf-8")
    finally:
        if temp_root.parent == root and temp_root.name.startswith(".tmp-msix-unpacked-"):
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


def test_release_dist_preflight_rejects_missing_japanese_ocr_notices():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the release preflight script")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "verify_release_dist.ps1"
    temp_root = root / f".tmp-msix-japanese-notices-{uuid.uuid4().hex}"
    fixture = temp_root / "CloudHime"
    try:
        _write_release_fixture(powershell, fixture)
        notice_path = fixture / "_internal" / "THIRD_PARTY_NOTICES.md"
        notice_path.write_text(
            "\n".join(
                (
                    "## Knowledge research providers",
                    "DDGS",
                    "click",
                    "primp",
                    "lxml",
                    "httpx",
                    "fake-useragent",
                    "certifi",
                    "Jina Reader",
                )
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-File", str(script), "-DistDir", str(fixture)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert result.returncode != 0
        assert "meikiocr" in (result.stdout + result.stderr).lower()
    finally:
        if temp_root.parent == root and temp_root.name.startswith(".tmp-msix-japanese-notices-"):
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
    assert 'verify_release_dist.ps1' in ci
    assert '-UnpackedMsix' in ci

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



def test_wack_wrapper_source_contract_and_parser():
    root = Path(__file__).resolve().parents[1]
    script_path = root / "packaging" / "test_wack.ps1"
    assert script_path.is_file(), "WACK wrapper is missing"
    script = script_path.read_text(encoding="utf-8")

    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for WACK wrapper parser validation")
    script_literal = str(script_path).replace("'", "''")
    result = subprocess.run(
        [
            powershell, "-NoLogo", "-NoProfile", "-Command",
            f"$tokens = $null; $errors = $null; [System.Management.Automation.Language.Parser]::ParseFile('{script_literal}', [ref]$tokens, [ref]$errors) | Out-Null; if ($errors.Count) {{ $errors | ForEach-Object {{ $_.Message }}; exit 1 }}",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr


    assert "[CmdletBinding(DefaultParameterSetName = 'AppxPackagePath')]" in script
    assert "[Parameter(Mandatory = $true, ParameterSetName = 'AppxPackagePath')]" in script
    assert "[Parameter(Mandatory = $true, ParameterSetName = 'PackageFullName')]" in script
    assert "[Parameter(Mandatory = $true)]" in script
    assert "[string]$AppxPackagePath" in script
    assert "[string]$PackageFullName" in script
    assert "[string]$ReportOutputPath" in script
    assert "[string]$AppCertPath = 'C:\\Program Files (x86)\\Windows Kits\\10\\App Certification Kit\\appcert.exe'" in script

    assert "Get-Process -IncludeUserName" not in script
    assert "Get-Process" not in script
    assert "[System.Diagnostics.Process]::GetCurrentProcess().SessionId" in script
    assert "[Environment]::UserInteractive" in script
    assert "WindowsPrincipal" in script
    assert "WindowsBuiltInRole]::Administrator" in script
    assert script.index("[Environment]::UserInteractive") < script.index("WindowsPrincipal")
    assert "WindowsPowerShell\\v1.0\\powershell.exe" in script

    assert "$AppxPackagePath = (Resolve-Path -LiteralPath $AppxPackagePath -ErrorAction Stop).Path" in script
    assert "$AppCertPath = (Resolve-Path -LiteralPath $AppCertPath -ErrorAction Stop).Path" in script
    assert "$ReportOutputPath = [System.IO.Path]::GetFullPath($ReportOutputPath)" in script
    assert "GetExtension($ReportOutputPath) -ine '.xml'" in script
    assert "Test-Path -LiteralPath $reportParent -PathType Container" in script
    assert "Test-Path -LiteralPath $ReportOutputPath" in script
    assert "Get-AppxPackage" in script
    assert "PackageFullName -ceq $PackageFullName" in script
    assert "(?i)\\.(msix|appx|msixbundle|appxbundle)$" in script

    reset_index = script.index("& $AppCertPath reset")
    package_test = "& $AppCertPath test -appxpackagepath $AppxPackagePath -reportoutputpath $ReportOutputPath"
    installed_test = "& $AppCertPath test -packagefullname $PackageFullName -reportoutputpath $ReportOutputPath"
    assert package_test in script
    assert installed_test in script
    assert reset_index < script.index(package_test)
    assert reset_index < script.index(installed_test)
    assert script.count("if ($LASTEXITCODE -ne 0)") >= 2

    assert "-Encoding UTF8" not in script
    assert "[System.Xml.XmlDocument]::new()" in script
    assert "$report.Load($ReportOutputPath)" in script
    assert 'SelectNodes("/REPORT/@OVERALL_RESULT")' in script
    assert 'SelectNodes("//RESULT/@OVERALL_RESULT")' not in script
    assert "$overallResults.Count -ne 1" in script
    assert "$overallResult -ine 'PASS'" in script
    for forbidden in (
        "New-SelfSignedCertificate", "Import-Certificate", "signtool",
        "Add-AppxPackage", "Remove-AppxPackage", "-AllUsers", "Start-Process",
    ):
        assert forbidden.lower() not in script.lower()


def test_wack_core_bridge_forwards_explicit_parameter_set_arguments():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "test_wack.ps1").read_text(encoding="utf-8")

    assert "if ($PSCmdlet.ParameterSetName -eq 'AppxPackagePath')" in script
    assert "'-AppxPackagePath', $AppxPackagePath" in script
    assert "'-PackageFullName', $PackageFullName" in script
    assert "'-ReportOutputPath', $ReportOutputPath" in script
    assert "'-AppCertPath', $AppCertPath" in script
    assert "$PSBoundParameters.GetEnumerator()" not in script


def test_wack_core_bridge_reparses_one_parameter_set_without_ambiguity(tmp_path):
    powershell = shutil.which("pwsh")
    if not powershell:
        pytest.skip("PowerShell 7 is required for WACK bridge validation")

    root = Path(__file__).resolve().parents[1]
    script_path = root / "packaging" / "test_wack.ps1"
    report_path = tmp_path / "bridge-probe.xml"
    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(script_path),
            "-PackageFullName",
            "CloudHime_1.0.0.0_x64__publisherid",
            "-ReportOutputPath",
            str(report_path),
            "-AppCertPath",
            str(tmp_path / "missing-appcert.exe"),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "AmbiguousParameterSet" not in output
    assert "WACK requires an elevated Administrator session" in output or "appcert.exe was not found" in output
    assert not report_path.exists()

def test_wack_report_reads_root_overall_result_attribute(tmp_path):
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for WACK report schema validation")

    report_path = tmp_path / "wack-report.xml"
    report_path.write_text(
        "<REPORT OVERALL_RESULT=\"PASS\"><REQUIREMENTS><TEST><RESULT>FAIL</RESULT></TEST></REQUIREMENTS></REPORT>",
        encoding="utf-8",
    )
    report_literal = str(report_path).replace("'", "''")
    command = (
        "$report = [System.Xml.XmlDocument]::new(); "
        f"$report.Load('{report_literal}'); "
        "$overallResults = @($report.SelectNodes('/REPORT/@OVERALL_RESULT')); "
        "if ($overallResults.Count -ne 1 -or $overallResults[0].Value -cne 'PASS') { exit 1 }; "
        "Write-Output $overallResults[0].Value"
    )
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "PASS"

def test_wack_readme_sets_optional_deprecated_partner_center_boundary():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "packaging" / "README.md").read_text(encoding="utf-8").lower()

    assert "wack" in readme
    assert "deprecated" in readme
    assert "optional local pre-submission check" in readme
    assert "partner center" in readme
    assert "final gate" in readme
    assert "test_msix_install.ps1" in readme
    assert "try/finally" in readme
    assert "admin" in readme
    assert "active" in readme
    assert "appcert.exe reset" in readme
    assert "appcert.exe test -appxpackagepath" in readme
    assert "appcert.exe test -packagefullname" in readme


def test_store_identity_config_is_local_only_and_documented():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "packaging" / "README.md").read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert "packaging/store-identity.local.json" in gitignore
    assert "-StoreIdentityConfigPath" in readme
    assert "Partner Center" in readme
    assert "StoreRelease" in readme

def test_store_release_requires_a_controlled_identity_config():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "build_msix.ps1").read_text(encoding="utf-8")

    for marker in (
        "[switch]$StoreRelease",
        "[string]$StoreIdentityConfigPath",
        "StoreRelease requires -StoreIdentityConfigPath",
        "package_family_name",
        "[\\s._-]",
    ):
        assert marker in script


def test_store_release_rejects_missing_identity_config_before_preflight():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the Store identity guard test")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "build_msix.ps1"
    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(script),
            "-StoreRelease",
            "-PreflightOnly",
            "-DistDir",
            str(root / "missing-store-release-dist"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "StoreRelease requires -StoreIdentityConfigPath" in combined

def test_store_release_rejects_placeholder_publisher_before_preflight():
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for the Store identity guard test")

    root = Path(__file__).resolve().parents[1]
    script = root / "packaging" / "build_msix.ps1"
    config_path = root / f".tmp-store-identity-{uuid.uuid4().hex}.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "identity_name": "CloudHime",
                "publisher": "CN=CloudHime Development",
                "publisher_display_name": "CloudHime",
                "package_family_name": "CloudHime_1234567890123",
            }
        ),
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-File",
                str(script),
                "-StoreRelease",
                "-StoreIdentityConfigPath",
                str(config_path),
                "-PreflightOnly",
                "-DistDir",
                str(root / "missing-store-release-dist"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        config_path.unlink(missing_ok=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "StoreRelease rejects development" in combined
