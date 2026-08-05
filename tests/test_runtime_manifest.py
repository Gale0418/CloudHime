import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


_MODULE_PATH = Path(__file__).resolve().parents[1] / "packaging" / "runtime_manifest.py"
_SPEC = importlib.util.spec_from_file_location("cloudhime_runtime_manifest", _MODULE_PATH)
_RUNTIME_MANIFEST = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RUNTIME_MANIFEST)

build_manifest = _RUNTIME_MANIFEST.build_manifest
validate_manifest = _RUNTIME_MANIFEST.validate_manifest


def _write_runtime(root):
    root.mkdir()
    (root / "llama-server.exe").write_bytes(b"server")
    (root / "ggml-cuda.dll").write_bytes(b"cuda")
    (root / "nested").mkdir()
    (root / "nested" / "helper.dll").write_bytes(b"helper")


def test_runtime_manifest_round_trip_records_metadata_and_hashes(tmp_path):
    runtime = tmp_path / "runtime"
    _write_runtime(runtime)

    manifest = build_manifest(
        runtime,
        server_version="llama.cpp build 123",
        source_commit="abc123",
        backend="cuda",
        architecture="x64",
    )

    assert manifest["schema_version"] == 1
    assert manifest["runtime"] == "llama-server"
    assert manifest["server"]["version"] == "llama.cpp build 123"
    assert manifest["build"] == {
        "source_commit": "abc123",
        "backend": "cuda",
        "architecture": "x64",
    }
    assert [entry["path"] for entry in manifest["files"]] == [
        "ggml-cuda.dll",
        "llama-server.exe",
        "nested/helper.dll",
    ]
    server_entry = next(
        entry for entry in manifest["files"] if entry["path"] == "llama-server.exe"
    )
    assert server_entry["size"] == 6
    assert server_entry["sha256"] == hashlib.sha256(b"server").hexdigest()

    validate_manifest(runtime, manifest)


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (
            lambda manifest, runtime: manifest["files"][0].update({"sha256": "0" * 64}),
            "hash or size mismatch",
        ),
        (
            lambda manifest, runtime: (runtime / "unexpected.dll").write_bytes(b"new"),
            "file set mismatch",
        ),
        (
            lambda manifest, runtime: (runtime / "ggml-cuda.dll").unlink(),
            "file set mismatch",
        ),
    ],
)
def test_runtime_manifest_rejects_artifact_drift(tmp_path, mutate, expected):
    runtime = tmp_path / "runtime"
    _write_runtime(runtime)
    manifest = build_manifest(
        runtime,
        server_version="fixture",
        source_commit="fixture",
        backend="cuda",
        architecture="x64",
    )

    mutate(manifest, runtime)

    with pytest.raises(ValueError, match=expected):
        validate_manifest(runtime, manifest)


def test_runtime_manifest_rejects_missing_metadata(tmp_path):
    runtime = tmp_path / "runtime"
    _write_runtime(runtime)
    manifest = build_manifest(
        runtime,
        server_version="fixture",
        source_commit="fixture",
        backend="cuda",
        architecture="x64",
    )
    manifest["build"]["source_commit"] = ""

    with pytest.raises(ValueError, match="metadata"):
        validate_manifest(runtime, manifest)


def test_runtime_manifest_is_json_safe(tmp_path):
    runtime = tmp_path / "runtime"
    _write_runtime(runtime)
    manifest = build_manifest(
        runtime,
        server_version="日文版 build",
        source_commit="fixture",
        backend="cuda",
        architecture="x64",
    )

    encoded = json.dumps(manifest, ensure_ascii=False)
    assert "日文版 build" in encoded
