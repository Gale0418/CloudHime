import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

import pytest


RUNTIME_FILES = (
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


def test_release_build_contract_has_required_resources():
    root = Path(__file__).resolve().parents[1]
    script = (root / "build_exe.bat").read_text(encoding="utf-8")
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")

    assert "('assets', 'assets')" in spec
    assert "('dictionary.json', '.')" in spec
    assert "('LICENSE', '.')" in spec
    assert "('THIRD_PARTY_NOTICES.md', '.')" in spec
    assert "('build\\\\runtime', 'runtime')" in spec
    for production_module in ("CloudHime.py", "cloudhime_core.py", "cloudhime_ui.py", "cloudhime_workers.py"):
        source = (root / production_module).read_text(encoding="utf-8")
        assert "LocalGemmaProvider" not in source
    assert 'bubble_qss.txt' not in spec
    for optional_module in ('tensorflow', 'keras', 'h5py', 'tensorboard', 'jax', 'jaxlib'):
        assert optional_module in spec
    assert (root / 'LICENSE').is_file()
    assert (root / 'THIRD_PARTY_NOTICES.md').is_file()

    missing_runtime = [
        filename for filename in RUNTIME_FILES
        if not (root / "runtime" / filename).is_file()
    ]
    if missing_runtime:
        pytest.skip("runtime/ is a local release artifact; CI uses the MSIX contract job")
    for filename in RUNTIME_FILES:
        assert (root / "runtime" / filename).is_file()


def test_release_build_isolated_from_incompatible_powershell_module_path():
    root = Path(__file__).resolve().parents[1]
    script = (root / "build_exe.bat").read_text(encoding="utf-8")

    module_guard = 'set "PSModulePath=%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\Modules;%ProgramFiles%\\WindowsPowerShell\\Modules"'
    assert 'set "CLOUDHIME_ORIGINAL_PS_MODULE_PATH=%PSModulePath%"' in script
    assert module_guard in script
    assert script.index(module_guard) < script.index("powershell -NoProfile")
    assert 'set "PSModulePath=%CLOUDHIME_ORIGINAL_PS_MODULE_PATH%"' in script

def test_runtime_manifest_is_generated_and_verified():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")
    verifier = (root / "packaging" / "verify_release_dist.ps1").read_text(encoding="utf-8")

    assert (root / "packaging" / "runtime_manifest.py").is_file()
    assert "runtime_manifest.py" in build_script
    assert "--version" in (root / "packaging" / "runtime_manifest.py").read_text(
        encoding="utf-8"
    )
    assert "runtime-manifest.json" in verifier
    assert "Get-Sha256Hex" in verifier
    assert "file set mismatch" in verifier

def test_release_verifier_uses_streaming_sha256_without_get_file_hash():
    root = Path(__file__).resolve().parents[1]
    verifier = (root / "packaging" / "verify_release_dist.ps1").read_text(encoding="utf-8")

    assert "function Get-Sha256Hex" in verifier
    assert "SequentialScan" in verifier
    assert "1048576" in verifier
    assert "Get-FileHash" not in verifier

def test_production_requirements_are_exactly_version_pinned():
    root = Path(__file__).resolve().parents[1]
    for filename in ("requirements.txt", "requirements-ci.txt"):
        requirements = (root / filename).read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in requirements
            if line.strip() and not line.lstrip().startswith("#")
        ]
        assert entries
        assert all("==" in entry for entry in entries), filename

def test_release_build_uses_a_separate_hash_pinned_tool_lock():
    root = Path(__file__).resolve().parents[1]
    build_lock_path = root / "requirements-build-win-amd64-py310.txt"
    build_lock = build_lock_path.read_text(encoding="utf-8")
    entries = [
        line.strip()
        for line in build_lock.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    names = {line.split("==", 1)[0].lower().replace("_", "-") for line in entries}

    assert entries
    assert names == {
        "altgraph",
        "packaging",
        "pefile",
        "pyinstaller",
        "pyinstaller-hooks-contrib",
        "pywin32-ctypes",
        "setuptools",
    }
    assert all("==" in line for line in entries)
    assert all(re.search(r"--hash=sha256:[0-9a-f]{64}$", line) for line in entries)

    production = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pyinstaller" not in production
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")
    assert 'set "BUILD_REQUIREMENTS=requirements-build-win-amd64-py310.txt"' in build_script
    assert "%BUILD_REQUIREMENTS%" in build_script
    assert "--require-hashes" in build_script

def _powershell_executable():
    return shutil.which("pwsh") or shutil.which("powershell")


def test_runtime_fetch_gate_stages_a_hash_verified_local_archive(tmp_path):
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for runtime fetch integration coverage")

    root = Path(__file__).resolve().parents[1]
    archive = tmp_path / "llama-runtime.zip"
    output = tmp_path / "runtime"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("llama-runtime/llama-server.exe", b"server-binary")
        bundle.writestr("llama-runtime/llama.dll", b"runtime-binary")
    expected_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()

    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(root / "packaging" / "fetch_runtime_assets.ps1"),
            "-ArchivePath",
            str(archive),
            "-ExpectedSha256",
            expected_sha256,
            "-SourceCommit",
            "a" * 40,
            "-OutputRuntimeDir",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output / "llama-server.exe").read_bytes() == b"server-binary"
    assert (output / "llama-runtime-commit.txt").read_text(encoding="utf-8").strip() == "a" * 40
    metadata = json.loads((output / "runtime-source.json").read_text(encoding="utf-8"))
    assert metadata == {
        "schema_version": 1,
        "source_commit": "a" * 40,
        "archive_sha256": expected_sha256,
        "backend": "cuda",
        "architecture": "x64",
    }


def test_runtime_fetch_gate_rejects_bad_hash_and_zip_traversal(tmp_path):
    powershell = _powershell_executable()
    if not powershell:
        pytest.skip("PowerShell is required for runtime fetch integration coverage")

    root = Path(__file__).resolve().parents[1]
    script = str(root / "packaging" / "fetch_runtime_assets.ps1")
    archive = tmp_path / "unsafe-runtime.zip"
    output = tmp_path / "runtime"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("../escaped.txt", b"must-not-extract")
        bundle.writestr("llama-runtime/llama-server.exe", b"server-binary")
    expected_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()

    bad_hash = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-File",
            script,
            "-ArchivePath",
            str(archive),
            "-ExpectedSha256",
            "0" * 64,
            "-SourceCommit",
            "b" * 40,
            "-OutputRuntimeDir",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert bad_hash.returncode != 0
    assert "sha-256 mismatch" in (bad_hash.stdout + bad_hash.stderr).lower()
    assert not output.exists()

    traversal = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-File",
            script,
            "-ArchivePath",
            str(archive),
            "-ExpectedSha256",
            expected_sha256,
            "-SourceCommit",
            "b" * 40,
            "-OutputRuntimeDir",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert traversal.returncode != 0
    assert "path traversal" in (traversal.stdout + traversal.stderr).lower()
    assert not output.exists()

def test_production_release_excludes_in_process_llama_binding():
    root = Path(__file__).resolve().parents[1]
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    dev_requirements = (root / "requirements-llama-dev.txt").read_text(encoding="utf-8")
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")

    assert "llama-cpp-python" not in requirements
    assert "llama-cpp-python==0.3.16" in dev_requirements
    excludes = spec.split("excludes=[", 1)[1].split("]", 1)[0]
    assert "llama_cpp" in excludes
    assert "_llama_cpp" in excludes
    for dev_only_module in ("pytest", "pytest-qt", "pluggy", "iniconfig", "pygments"):
        assert dev_only_module in excludes
    assert "('build\\\\runtime', 'runtime')" in spec
    for production_module in ("CloudHime.py", "cloudhime_core.py", "cloudhime_ui.py", "cloudhime_workers.py"):
        source = (root / production_module).read_text(encoding="utf-8")
        assert "LocalGemmaProvider" not in source


def test_spec_filters_runtime_dependency_duplicates_from_analysis_binaries():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")

    assert "runtime_source_dir" in spec
    assert "a.binaries = [" in spec
    assert "_is_duplicate_runtime_binary" in spec
    assert "source_path.is_relative_to(runtime_source_dir)" in spec
    assert "destination_path.parts[0].casefold() != \"runtime\"" in spec

def test_source_bootstrap_does_not_require_external_model_service():
    root = Path(__file__).resolve().parents[1]
    install_script = (root / "install.ps1").read_text(encoding="utf-8")
    run_script = (root / "run.bat").read_text(encoding="utf-8")

    assert "Miniconda" not in install_script
    assert "Ollama" in install_script
    assert "--version" in install_script
    assert "pythonMajor" in install_script
    assert "CONDA_PATH" not in run_script
    assert r".venv\Scripts\python.exe" in run_script

def test_release_bundle_includes_knowledge_search_dependency_and_notice():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")
    notices = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert "--collect-all ddgs" not in build_script
    assert "import ddgs, lxml, primp, fake_useragent, certifi" in build_script
    assert "--exclude-module lxml" not in spec
    assert "collect_all" not in spec
    assert "collect_submodules" in spec
    assert "collect_data_files" in spec
    assert "ddgs.ddgs" in spec
    assert "fake_useragent_datas" in spec
    assert "certifi_datas" in spec
    assert "*fake_useragent_datas, *certifi_datas" in spec
    assert "ddgs_datas" not in spec
    assert "ddgs.dht" not in spec
    assert "ddgs.api_server" not in spec
    for argument in ("lxml.html", "lxml.etree"):
        assert argument in spec
    assert "lxml" not in spec.split("excludes=[", 1)[1].split("]", 1)[0]
    assert "ddgs" in notices.lower()
    assert "9.14.4" in notices
    assert "MIT" in notices
    assert "lxml" in notices.lower()
    assert "BSD" in notices
    assert "libxml2" in notices
    assert "libxslt" in notices
    for dependency in ("click", "primp", "httpx", "fake-useragent", "certifi"):
        assert dependency in notices

def test_release_build_runs_frozen_dependency_smoke_before_preflight():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")
    app_source = (root / "CloudHime.py").read_text(encoding="utf-8")

    smoke_env = "CLOUDHIME_PACKAGED_IMPORT_SMOKE"
    required_modules = (
        "ddgs",
        "lxml",
        "primp",
        "fake_useragent",
        "certifi",
        "meikiocr.ocr",
        "onnxruntime",
    )
    assert smoke_env in app_source
    assert "run_packaged_import_smoke" in app_source
    smoke_call_index = app_source.index("if run_packaged_import_smoke():")
    assert smoke_call_index < app_source.index("QApplication(sys.argv)")
    for module_name in required_modules:
        assert module_name in app_source

    smoke_index = build_script.index('"%DIST_DIR%\\CloudHime.exe"')
    preflight_index = build_script.index("packaging\\verify_release_dist.ps1")
    assert smoke_index < preflight_index
    assert f'set "{smoke_env}=1"' in build_script
    assert f'set "{smoke_env}="' in build_script[smoke_index:]

def test_release_build_uses_locked_python_major_minor_for_packaging_steps():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")

    assert 'set "PYTHON=py -3.10-64"' in build_script
    python_commands = [
        line.strip()
        for line in build_script.splitlines()
        if line.strip().startswith("python ")
    ]
    assert python_commands == []
    assert "%PYTHON% -m PyInstaller" in build_script
    assert "%PYTHON% packaging\\runtime_manifest.py" in build_script
    assert "%PYTHON% -c \"import platform, sys" in build_script
    normalized_script = build_script.replace("\r\n", "\n")
    assert 'set "BUILD_EXIT_CODE=0"\nset "PYTHON=py -3.10-64"' in normalized_script

def test_release_build_uses_the_spec_as_packaging_source_of_truth():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")
    build_start = build_script.index("echo Building %APP_NAME% release...")
    build_end = build_script.index("powershell -NoProfile", build_start)
    build_command = build_script[build_start:build_end]

    assert "CloudHime.spec" in build_command
    assert "CloudHime.py" not in build_command


def test_release_build_runs_preflight_before_creating_zip():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")

    pyinstaller_index = build_script.index("%PYTHON% -m PyInstaller --noconfirm --clean CloudHime.spec")
    preflight_index = build_script.index("packaging\\verify_release_dist.ps1")
    zip_index = build_script.index("Compress-Archive")
    assert pyinstaller_index < preflight_index < zip_index
    assert "Release preflight failed." in build_script[preflight_index:zip_index]


def test_release_build_stages_dependency_provenance_before_pyinstaller_and_specs_it():
    root = Path(__file__).resolve().parents[1]
    build_script = (root / "build_exe.bat").read_text(encoding="utf-8")
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")

    prepare = build_script.index("packaging\\prepare_release_provenance.ps1")
    pyinstaller = build_script.index("%PYTHON% -m PyInstaller --noconfirm")
    assert prepare < pyinstaller
    assert "provenance" in spec
    assert (root / "packaging" / "prepare_release_provenance.ps1").is_file()

def test_release_build_requires_explicit_llama_runtime_provenance():
    root = Path(__file__).resolve().parents[1]
    script = (root / "build_exe.bat").read_text(encoding="utf-8")
    normalized = script.replace("\r\n", "\n")

    assert "LLAMA_RUNTIME_COMMIT" in script
    assert "runtime\\llama-runtime-commit.txt" in normalized
    assert "runtime\\runtime-source.json" in normalized
    assert "Missing explicit llama runtime commit provenance." in script
    assert "git rev-parse HEAD" not in script

def test_release_build_uses_explicit_bounded_manifest_timeout_and_resolvable_cleanup():
    root = Path(__file__).resolve().parents[1]
    script = (root / "build_exe.bat").read_text(encoding="utf-8")

    manifest_command = next(
        line for line in script.splitlines() if "packaging\\runtime_manifest.py" in line
    )
    assert "--version-timeout 120" in manifest_command

    failure_label = ":failure"
    cleanup_label = ":cleanup"
    failure_label_index = script.index("\n:failure") + 1
    cleanup_label_index = script.index("\n:cleanup") + 1
    assert script.splitlines().count(failure_label) == 1
    assert script.splitlines().count(cleanup_label) == 1
    assert failure_label_index > script.index(manifest_command)
    assert failure_label_index < cleanup_label_index
    assert script.count("goto :failure") >= 1
    assert "set \"BUILD_EXIT_CODE=1\"" in script[
        failure_label_index:cleanup_label_index
    ]
    assert "goto :cleanup" in script[:failure_label_index]
    assert "goto :cleanup" in script[failure_label_index:cleanup_label_index]
    assert "exit /b 1" in script[cleanup_label_index:]


def test_clean_machine_smoke_script_is_environment_isolated_and_exact_cleanup():
    root = Path(__file__).resolve().parents[1]
    script_path = root / "packaging" / "test_clean_machine.ps1"
    assert script_path.is_file(), "clean-machine smoke script is missing"
    script = script_path.read_text(encoding="utf-8")

    for marker in (
        "ProcessStartInfo",
        "$processEnvironment.Clear()",
        "SystemRoot",
        "LOCALAPPDATA",
        "PATH",
        "LaunchWaitSeconds",
        "Kill()",
        "WaitForExit",
        "Get-Process -Id",
        "InvalidOperationException",
    ):
        assert marker in script
    assert "CLOUDHIME_PACKAGED_IMPORT_SMOKE" not in script
    assert "Start-Process" not in script
    assert "Ollama" not in script
    assert "Conda" not in script
    assert "python.exe" not in script.lower()


def test_release_spec_keeps_lazy_japanese_ocr_runtime_modules():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")

    hidden_imports = spec.split("japanese_ocr_hiddenimports = [", 1)[1].split("]", 1)[0]
    for module_name in ("meikiocr", "meikiocr.ocr", "onnxruntime"):
        assert f'"{module_name}"' in hidden_imports
    assert "*japanese_ocr_hiddenimports" in spec

def test_production_translation_provider_has_no_inprocess_llama_path():
    root = Path(__file__).resolve().parents[1]
    production_source = (root / "translation_providers.py").read_text(encoding="utf-8")
    dev_source = (root / "dev_local_gemma_provider.py").read_text(encoding="utf-8")

    assert "LocalGemmaProvider" not in production_source
    assert "from llama_cpp import Llama" not in production_source
    assert "class LocalGemmaProvider" in dev_source
    assert "from llama_cpp import Llama" in dev_source


def test_clean_machine_uses_unique_user_sandbox_and_owned_descendant_cleanup():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "test_clean_machine.ps1").read_text(encoding="utf-8")

    assert "cloudhime-clean-machine-" in script
    assert "$sandboxRoot" in script
    assert "LOCALAPPDATA = $localAppData" in script
    assert "APPDATA = $appData" in script
    assert "TEMP = $tempRoot" in script
    assert "TMP = $tempRoot" in script
    assert "Get-CimInstance Win32_Process" in script
    assert "CreateToolhelp32Snapshot" in script
    assert "GetParentMap" in script
    assert "Stop-OwnedDescendants" in script
    assert "ParentProcessId" in script
    assert "Stop-Process -Id $descendantId" in script
    assert "Remove-Item -LiteralPath $sandboxRoot" in script


def test_clean_machine_script_exposes_packaged_functional_mode():
    root = Path(__file__).resolve().parents[1]
    script = (root / "packaging" / "test_clean_machine.ps1").read_text(encoding="utf-8")

    assert "FunctionalSmoke" in script
    assert "FunctionalTimeoutSeconds" in script
    assert "AdditionalEnvironmentVariables" in script
    assert "Packaged functional smoke failed" in script


def test_frozen_spec_bundles_runtime_manifest_for_packaged_functional_smoke():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "CloudHime.spec").read_text(encoding="utf-8")
    entry = (root / "CloudHime.py").read_text(encoding="utf-8")

    assert r"packaging\\runtime_manifest.py" in spec
    assert "run_packaged_functional_smoke" in entry
