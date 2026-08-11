from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import vision_product_path_benchmark as benchmark


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _manifest(image: Path, image_bytes: bytes, *, locked: bool = True) -> dict:
    return {
        "version": 1,
        "dataset": "product-path",
        "description": "test fixture",
        "schema": {"required_case_fields": []},
        "cases": [{
            "id": "case-1", "source_group": "fixture", "image": str(image),
            "split": "test" if locked else "dev", "source_lang": "en", "target_lang": "zh-Hant",
            "reference_source": "source", "reference_translations": ["翻譯"],
            "required_terms": [], "source_family": "fixture", "image_sha256": _sha(image_bytes),
            "annotation_revision": "1", "usage_status": "locked_test" if locked else "development",
            "ground_truth_confirmed_by_owner": locked,
        }],
    }


def _assets(tmp_path: Path) -> SimpleNamespace:
    server = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    projector = tmp_path / "projector.gguf"
    for path in (server, model, projector):
        path.write_bytes(b"asset")
    return SimpleNamespace(server_path=server, model_path=model, projector_path=projector)


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_preflight_never_constructs_worker_and_checks_unicode_image(monkeypatch, tmp_path):
    image = tmp_path / "繁體圖片.png"
    image_bytes = b"png-bytes"
    image.write_bytes(image_bytes)
    manifest_path = _write_manifest(tmp_path, _manifest(image, image_bytes))
    verified = []
    monkeypatch.setattr(benchmark, "validate_benchmark_lock", lambda *_: {"ok": True, "errors": []})
    monkeypatch.setattr(benchmark, "resolve_preferred_vision_assets", lambda _: _assets(tmp_path))
    monkeypatch.setattr(benchmark, "verify_asset", lambda path, sha, size: verified.append((path, sha, size)))
    monkeypatch.setattr(benchmark, "_sha256_file", lambda path: benchmark.ASSET_SHA256.get({
        "llama-server.exe": "server_path", "model.gguf": "model_path", "projector.gguf": "projector_path",
    }[path.name]) or "a" * 64)
    monkeypatch.setattr(benchmark, "_prompt_bundle_sha256", lambda: "d" * 64)
    monkeypatch.setattr(benchmark, "OCRWorker", lambda: pytest.fail("preflight must not create OCRWorker"))

    result = benchmark.preflight(manifest_path)

    assert result["ok"] is True
    assert len(verified) == 3


def test_conditions_are_identical_except_route_and_runtime_profile(monkeypatch, tmp_path):
    assets = _assets(tmp_path)
    monkeypatch.setattr(benchmark, "resolve_preferred_vision_assets", lambda _: assets)
    monkeypatch.setattr(benchmark, "_verify_assets", lambda _: {
        "server_path": "a" * 64, "model_path": "b" * 64, "projector_path": "c" * 64,
    })
    monkeypatch.setattr(benchmark, "_prompt_bundle_sha256", lambda: "d" * 64)

    baseline, candidate = benchmark.build_conditions(assets)

    assert baseline["route"] == "baseline" and baseline["runtime_profile"] == "text"
    assert candidate["route"] == "candidate" and candidate["runtime_profile"] == "vision"
    assert {key: value for key, value in baseline.items() if key not in {"route", "runtime_profile"}} == {key: value for key, value in candidate.items() if key not in {"route", "runtime_profile"}}
    assert baseline["model_sha256"] == "b" * 64
    assert baseline["context"] == {"n_ctx": 4096}
    assert baseline["sampling"] == {"temperature": 0, "repeat_penalty": 1.15}
    assert baseline["target"] == "zh-TW"


def test_conditions_record_optional_vision_width_as_a_fixed_experiment_control(
    monkeypatch, tmp_path
):
    assets = _assets(tmp_path)
    monkeypatch.setattr(benchmark, "resolve_preferred_vision_assets", lambda _: assets)
    monkeypatch.setattr(benchmark, "_verify_assets", lambda _: {
        "server_path": "a" * 64, "model_path": "b" * 64, "projector_path": "c" * 64,
    })
    monkeypatch.setattr(benchmark, "_prompt_bundle_sha256", lambda: "d" * 64)

    baseline, candidate = benchmark.build_conditions(assets, vision_image_max_width=896)

    assert baseline["vision_image_max_width"] == 896
    assert candidate["vision_image_max_width"] == 896
    assert benchmark.condition_fingerprint(baseline) == benchmark.condition_fingerprint(candidate)


def test_unicode_image_loader_uses_path_bytes_and_cv2_imdecode(monkeypatch, tmp_path):
    image = tmp_path / "測試影像.png"
    image.write_bytes(b"encoded")
    received = {}
    monkeypatch.setattr(benchmark.cv2, "imdecode", lambda payload, flags: received.update(payload=payload, flags=flags) or "pixels")

    pixels, raw = benchmark.load_image({"image": str(image)})

    assert pixels == "pixels" and raw == b"encoded"
    assert isinstance(received["payload"], np.ndarray)
    assert received["payload"].tobytes() == b"encoded"


def test_run_prints_only_redacted_evaluator_json_and_cannot_inject_cpu_or_endpoint(monkeypatch, tmp_path, capsys):
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    manifest_path = _write_manifest(tmp_path, _manifest(image, b"image"))
    assets = _assets(tmp_path)
    captured = {}
    asset_hashes = {"server_path": "a" * 64, "model_path": "b" * 64, "projector_path": "c" * 64}
    monkeypatch.setattr(benchmark, "_verify_assets", lambda _: asset_hashes)
    monkeypatch.setattr(benchmark, "_prompt_bundle_sha256", lambda: "d" * 64)
    baseline, candidate = benchmark.build_conditions(assets)
    monkeypatch.setattr(benchmark, "preflight", lambda _: {"ok": True, "assets": assets, "manifest": _manifest(image, b"image"), "baseline": baseline, "candidate": candidate})
    monkeypatch.setattr(benchmark, "evaluate_product_path_pair", lambda manifest, baseline, candidate, **kwargs: captured.update(manifest=manifest, baseline=baseline, candidate=candidate, kwargs=kwargs) or {"records": [{"detected_source": "secret", "translation": "secret", "ok": True}]})

    assert benchmark.main(["--manifest", str(manifest_path), "--startup-timeout", "7"]) == 0

    emitted = json.loads(capsys.readouterr().out)
    assert emitted == {"records": [{"ok": True}], "metadata": {
        "execution_order": "baseline_then_candidate", "latency_order_balanced": False,
    }}
    assert captured["baseline"]["gpu_mode"] == "gpu"
    assert "base_url" not in captured["baseline"] and "cpu_only" not in captured["candidate"]
    assert captured["kwargs"]["session_factory"]()._timeout_seconds == 7


def test_runner_forwards_explicit_execution_order(monkeypatch, tmp_path, capsys):
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    manifest_path = _write_manifest(tmp_path, _manifest(image, b"image"))
    assets = _assets(tmp_path)
    captured = {}
    monkeypatch.setattr(benchmark, "_verify_assets", lambda _: {
        "server_path": "a" * 64,
        "model_path": "b" * 64,
        "projector_path": "c" * 64,
    })
    monkeypatch.setattr(benchmark, "_prompt_bundle_sha256", lambda: "d" * 64)
    baseline, candidate = benchmark.build_conditions(assets)
    monkeypatch.setattr(
        benchmark,
        "preflight",
        lambda _: {
            "ok": True,
            "assets": assets,
            "manifest": _manifest(image, b"image"),
            "baseline": baseline,
            "candidate": candidate,
        },
    )
    monkeypatch.setattr(
        benchmark,
        "evaluate_product_path_pair",
        lambda manifest, baseline, candidate, **kwargs: captured.update(
            kwargs=kwargs
        ) or {"records": []},
    )

    assert benchmark.main([
        "--manifest", str(manifest_path),
        "--execution-order", "candidate_then_baseline",
    ]) == 0

    emitted = json.loads(capsys.readouterr().out)
    assert emitted["metadata"] == {
        "execution_order": "candidate_then_baseline",
        "latency_order_balanced": False,
    }
    assert captured["kwargs"]["execution_order"] == "candidate_then_baseline"


def test_preflight_rejects_manifest_without_locked_owner_confirmed_case(monkeypatch, tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    manifest_path = _write_manifest(tmp_path, _manifest(image, b"image", locked=False))
    monkeypatch.setattr(benchmark, "validate_benchmark_lock", lambda *_: {"ok": True, "errors": []})

    with pytest.raises(ValueError, match="locked owner-confirmed"):
        benchmark.preflight(manifest_path)


@pytest.mark.parametrize("changed_name", benchmark._PROMPT_BUNDLE_FILES)
def test_prompt_bundle_hash_changes_when_any_prompt_dependency_changes(monkeypatch, tmp_path, changed_name):
    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    for name in benchmark._PROMPT_BUNDLE_FILES:
        (tmp_path / name).write_bytes(name.encode("utf-8"))

    before = benchmark._prompt_bundle_sha256()
    dependency = tmp_path / changed_name
    dependency.write_bytes(dependency.read_bytes() + b" changed")

    assert benchmark._prompt_bundle_sha256() != before


def test_preflight_rejects_wrong_model_hash_even_if_asset_verifier_is_mocked(monkeypatch, tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    manifest_path = _write_manifest(tmp_path, _manifest(image, b"image"))
    assets = _assets(tmp_path)
    monkeypatch.setattr(benchmark, "validate_benchmark_lock", lambda *_: {"ok": True})
    monkeypatch.setattr(benchmark, "resolve_preferred_vision_assets", lambda _: assets)
    monkeypatch.setattr(benchmark, "verify_asset", lambda *_: None)
    monkeypatch.setattr(benchmark, "_sha256_file", lambda path: "wrong" if path == assets.model_path else "a" * 64)

    with pytest.raises(ValueError, match="model_path sha256 mismatch"):
        benchmark.preflight(manifest_path)


def test_parser_exposes_no_context_or_sampling_switches():
    parser = benchmark.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--manifest", "fixture.json", "--n-ctx", "8192"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--manifest", "fixture.json", "--temperature", "0.7"])


def test_runner_stdout_and_errors_do_not_leak_raw_content_or_paths(monkeypatch, tmp_path, capsys):
    raw_path = str(tmp_path / "sensitive-image.png")
    monkeypatch.setattr(benchmark, "preflight", lambda _: {
        "ok": True, "manifest": {}, "assets": _assets(tmp_path), "baseline": {}, "candidate": {},
    })

    def noisy_failure(*_args, **_kwargs):
        print(f"raw-content {raw_path}")
        raise RuntimeError(raw_path)

    monkeypatch.setattr(benchmark, "evaluate_product_path_pair", noisy_failure)

    assert benchmark.main(["--manifest", raw_path]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert raw_path not in captured.err and "raw-content" not in captured.err
    assert captured.err == "benchmark_failed: RuntimeError\n"


def test_runner_emits_only_sanitized_trace_rejection_diagnostics(monkeypatch, capsys):
    monkeypatch.setattr(benchmark, "preflight", lambda _: {
        "ok": True, "manifest": {}, "assets": SimpleNamespace(), "baseline": {}, "candidate": {},
    })
    monkeypatch.setattr(
        benchmark,
        "evaluate_product_path_pair",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError(
                "scan trace rejected: reason=fallback stage=translation "
                "outcome=fallback provider=local error_code=translation_failed "
                "fallback=translation_region_vision_failed exception=ValueError"
            )
        ),
    )

    assert benchmark.main(["--manifest", "fixture.json"]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("benchmark_failed: ValueError: scan trace rejected:")
    assert "translation_region_vision_failed" in captured.err
