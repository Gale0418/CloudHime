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

    assert 'assets;assets' in script
    assert 'dictionary.json;.' in script
    assert 'LICENSE;.' in script
    assert 'THIRD_PARTY_NOTICES.md;.' in script
    assert '%RUNTIME_STAGE%;runtime' in script
    assert 'bubble_qss.txt' not in script
    for optional_module in ('tensorflow', 'keras', 'h5py', 'tensorboard', 'jax', 'jaxlib'):
        assert f'--exclude-module {optional_module}' in script
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
