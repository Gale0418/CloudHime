from pathlib import Path

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
    for production_module in ("cloudhime_ui.py", "cloudhime_workers.py"):
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
    assert "('build\\\\runtime', 'runtime')" in spec
    for production_module in ("cloudhime_ui.py", "cloudhime_workers.py"):
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

    pyinstaller_index = build_script.index("python -m PyInstaller")
    preflight_index = build_script.index("packaging\\verify_release_dist.ps1")
    zip_index = build_script.index("Compress-Archive")
    assert pyinstaller_index < preflight_index < zip_index
    assert "Release preflight failed." in build_script[preflight_index:zip_index]
