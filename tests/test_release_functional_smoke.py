from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

import release_functional_smoke as smoke


def _write_runtime(root: Path, *, version: str = "b314", server_size: int = 100_000) -> Path:
    runtime = root / "runtime"
    runtime.mkdir()
    server = runtime / "llama-server.exe"
    server.write_bytes(b"server-binary" * ((server_size // 13) + 1))
    manifest = {
        "schema_version": 1,
        "runtime": "llama-server",
        "server": {"path": "llama-server.exe", "version": version},
        "build": {
            "source_commit": "b314",
            "backend": "cuda",
            "architecture": "x64",
        },
        "files": [{
            "path": "llama-server.exe",
            "size": server.stat().st_size,
            "sha256": smoke._sha256(server),
        }],
    }
    (runtime / "runtime-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return runtime


def _write_assets(root: Path) -> tuple[Path, Path]:
    model = root / "model.gguf"
    projector = root / "projector.gguf"
    model.write_bytes(b"m" * 1_048_576)
    projector.write_bytes(b"p" * 1_048_576)
    return model, projector


def test_validate_release_inputs_rejects_ci_placeholder(tmp_path: Path) -> None:
    runtime = _write_runtime(tmp_path, version="CloudHime CI placeholder")
    model, projector = _write_assets(tmp_path)
    image = tmp_path / "sample.png"
    assert cv2.imwrite(str(image), np.zeros((16, 16, 3), dtype=np.uint8))

    with pytest.raises(smoke.ReleaseSmokeError, match="placeholder"):
        smoke.validate_release_inputs(runtime, model, projector, image)


def test_validate_release_inputs_accepts_real_contract(tmp_path: Path) -> None:
    runtime = _write_runtime(tmp_path)
    model, projector = _write_assets(tmp_path)
    image = tmp_path / "sample.png"
    assert cv2.imwrite(str(image), np.zeros((16, 16, 3), dtype=np.uint8))

    assets = smoke.validate_release_inputs(runtime, model, projector, image)

    assert assets.server_path == runtime / "llama-server.exe"
    assert assets.model_path == model
    assert assets.projector_path == projector


def test_release_smoke_passes_explicit_assets_and_image_to_benchmark(monkeypatch, tmp_path: Path) -> None:
    runtime = _write_runtime(tmp_path)
    model, projector = _write_assets(tmp_path)
    image = tmp_path / "sample.png"
    assert cv2.imwrite(str(image), np.zeros((16, 16, 3), dtype=np.uint8))
    captured = {}

    def fake_run(manifest_path, **kwargs):
        captured["manifest_path"] = Path(manifest_path)
        captured["manifest"] = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        captured.update(kwargs)
        return {
            "runtime_mode": "cpu",
            "image_count": 1,
            "case_count": 1,
            "successful_images": 1,
            "successful_cases": 1,
            "request_success_images": 1,
            "request_success_cases": 1,
            "evaluation_mode": "technical_coverage",
            "quality_basis": "coverage_only",
            "image_results": [{"actual": "read", "error": ""}],
        }

    monkeypatch.setattr(smoke, "run_smoke", fake_run)
    result = smoke.run_release_smoke(
        runtime,
        model,
        projector,
        image,
        require_gpu=False,
    )

    assert result["successful_images"] == 1
    assert captured["assets"].server_path == runtime / "llama-server.exe"
    assert captured["assets"].model_path == model
    assert captured["assets"].projector_path == projector
    manifest = captured["manifest"]
    assert manifest["evaluation_mode"] == "technical_coverage"
    assert manifest["cases"][0]["sample_source"] == str(image)


def test_functional_complete_rejects_missing_image_results() -> None:
    result = {
        "evaluation_mode": "technical_coverage",
        "image_count": 1,
        "case_count": 1,
        "request_success_images": 1,
        "request_success_cases": 1,
        "successful_images": 1,
        "successful_cases": 1,
        "image_results": [],
    }

    assert smoke._functional_complete(result) is False


def test_parser_requires_release_asset_arguments() -> None:
    parser = smoke.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

    args = parser.parse_args([
        "--runtime-dir", "runtime",
        "--model", "model.gguf",
        "--projector", "projector.gguf",
        "--image", "sample.png",
    ])
    assert args.runtime_dir == Path("runtime")
    assert args.require_gpu is False


def test_parser_exposes_validate_only() -> None:
    args = smoke.build_parser().parse_args([
        "--runtime-dir", "runtime",
        "--model", "model.gguf",
        "--projector", "projector.gguf",
        "--image", "sample.png",
        "--validate-only",
    ])

    assert args.validate_only is True


def test_packaged_functional_smoke_is_noop_without_opt_in():
    import packaged_functional_smoke as packaged

    assert packaged.run_packaged_functional_smoke(environ={}) is None


def test_packaged_functional_smoke_writes_redacted_success_summary(tmp_path):
    import json
    import packaged_functional_smoke as packaged

    result_path = tmp_path / "packaged-result.json"
    captured = {}

    def fake_runner(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {
            "runtime_mode": "gpu",
            "evaluation_mode": "technical_coverage",
            "image_count": 1,
            "case_count": 1,
            "successful_images": 1,
            "successful_cases": 1,
            "request_success_images": 1,
            "request_success_cases": 1,
            "image_results": [{"actual": "不要寫入結果的原文", "error": ""}],
        }

    environ = {
        packaged.PACKAGED_FUNCTIONAL_SMOKE_ENV: "1",
        packaged.PACKAGED_SMOKE_RESULT_PATH_ENV: str(result_path),
        packaged.PACKAGED_SMOKE_RUNTIME_DIR_ENV: "runtime",
        packaged.PACKAGED_SMOKE_MODEL_PATH_ENV: "model.gguf",
        packaged.PACKAGED_SMOKE_PROJECTOR_PATH_ENV: "mmproj.gguf",
        packaged.PACKAGED_SMOKE_IMAGE_PATH_ENV: "sample.png",
        packaged.PACKAGED_SMOKE_REQUIRE_GPU_ENV: "1",
    }

    assert packaged.run_packaged_functional_smoke(environ=environ, runner=fake_runner) == 0
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evaluation_mode"] == "technical_coverage"
    assert payload["successful_images"] == 1
    assert "不要寫入結果的原文" not in result_path.read_text(encoding="utf-8")
    assert captured["kwargs"]["require_gpu"] is True


def test_packaged_functional_smoke_writes_fail_closed_result(tmp_path):
    import json
    import packaged_functional_smoke as packaged

    result_path = tmp_path / "packaged-result.json"
    environ = {
        packaged.PACKAGED_FUNCTIONAL_SMOKE_ENV: "1",
        packaged.PACKAGED_SMOKE_RESULT_PATH_ENV: str(result_path),
    }

    def fail_runner(*args, **kwargs):
        raise RuntimeError("raw prompt must not be persisted")

    assert packaged.run_packaged_functional_smoke(environ=environ, runner=fail_runner) == 2
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload == {
        "error_code": "packaged_functional_smoke_failed",
        "schema_version": 1,
        "status": "failed",
    }
    assert "raw prompt" not in result_path.read_text(encoding="utf-8")
