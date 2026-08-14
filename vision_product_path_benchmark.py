"""Locked, GPU-only local product-path Vision benchmark runner.

This module deliberately fixes context and sampling; scan mode is an explicit paired experiment control.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from benchmark_lock import DEFAULT_LOCK_PATH, validate_benchmark_lock
from cloudhime_workers import OCRWorker
from local_vision_assets import (
    ASSET_MINIMUM_BYTES,
    ASSET_SHA256,
    GEMMA_MODEL_SHA256,
    resolve_preferred_vision_assets,
    verify_asset,
)
from vision_e2e_benchmark import (
    LOCKED_USAGE,
    canonical_sha256,
    condition_fingerprint,
    redact_report,
    validate_manifest,
)
from vision_product_path_collector import evaluate_product_path_pair
from vision_product_path_collector import EXECUTION_ORDERS
from vision_product_path_local_adapter import ProductPathLocalSession


PROJECT_ROOT = Path(__file__).resolve().parent
_PROMPT_POLICY = {
    "bundle": "product-path-local-v1",
    "ocr_backend": "windows",
    "fallbacks": "disabled",
    "translation": "local-only",
}
_PROMPT_POLICY_VERSION = "product-path-prompt-bundle-v2"
_PROMPT_BUNDLE_FILES = (
    "dictionary.json",
    "translation_helpers.py",
    "vision_region.py",
    "knowledge_prompt_context.py",
)
_FIXED_SAMPLING = {"temperature": 0, "repeat_penalty": 1.15}
_FIXED_CONTEXT = {"n_ctx": 4096}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prompt_bundle_sha256(root: Path | None = None) -> str:
    """Hash the policy and every local source file that can shape the prompt."""
    bundle_root = PROJECT_ROOT if root is None else root
    return canonical_sha256({
        "policy_version": _PROMPT_POLICY_VERSION,
        "policy": _PROMPT_POLICY,
        "files": {
            name: _sha256_file(bundle_root / name)
            for name in _PROMPT_BUNDLE_FILES
        },
    })


def _load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    return payload


def _image_path(case: Mapping[str, Any]) -> Path:
    raw = case.get("image")
    if not isinstance(raw, str) or not raw:
        raise ValueError("case image path is required")
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_image(case: Mapping[str, Any]) -> tuple[Any, bytes]:
    """Load using Path bytes plus OpenCV decoding, including Windows Unicode paths."""
    image_bytes = _image_path(case).read_bytes()
    pixels = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if pixels is None:
        raise ValueError("image_unreadable")
    return pixels, image_bytes


def _locked_cases(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    cases = validate_manifest(manifest)
    locked = [case for case in cases if case["usage_status"] in LOCKED_USAGE]
    if not locked:
        raise ValueError("manifest has no locked owner-confirmed case")
    return locked


def _verify_images(cases: list[Mapping[str, Any]]) -> None:
    for case in cases:
        image_bytes = _image_path(case).read_bytes()
        if _sha256_file_bytes(image_bytes) != case["image_sha256"]:
            raise ValueError(f"image_sha256 mismatch for case {case['id']}")


def _sha256_file_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify_assets(assets: Any) -> dict[str, str]:
    actual_hashes: dict[str, str] = {}
    for field in ("server_path", "model_path", "projector_path"):
        path = Path(getattr(assets, field))
        verify_asset(
            path,
            ASSET_SHA256[field],
            ASSET_MINIMUM_BYTES[field],
        )
        actual_hash = _sha256_file(path)
        expected_hash = ASSET_SHA256[field]
        if expected_hash is not None and actual_hash != expected_hash.lower():
            raise ValueError(f"{field} sha256 mismatch")
        actual_hashes[field] = actual_hash
    return actual_hashes


def build_conditions(
    assets: Any,
    *,
    asset_hashes: Mapping[str, str] | None = None,
    vision_image_max_width: int | None = None,
    scan_mode: str = "region",
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_scan_mode = str(scan_mode).strip().lower()
    if normalized_scan_mode not in {"region", "fullscreen"}:
        raise ValueError("scan_mode must be region or fullscreen")
    hashes = dict(asset_hashes) if asset_hashes is not None else _verify_assets(assets)
    fixed = {
        "model_sha256": hashes["model_path"],
        "runtime_sha256": hashes["server_path"],
        "prompt_sha256": _prompt_bundle_sha256(),
        "target": "zh-TW",
        "sampling": dict(_FIXED_SAMPLING),
        "context": dict(_FIXED_CONTEXT),
        "gpu_mode": "gpu",
        "scan_mode": normalized_scan_mode,
    }
    if vision_image_max_width is not None:
        fixed["vision_image_max_width"] = vision_image_max_width
    baseline = {**fixed, "route": "baseline", "runtime_profile": "text"}
    candidate = {**fixed, "route": "candidate", "runtime_profile": "vision"}
    if condition_fingerprint(baseline) != condition_fingerprint(candidate):
        raise AssertionError("paired conditions must have one fixed bundle hash")
    return baseline, candidate


def preflight(
    manifest_path: str | Path,
    *,
    lock_path: str | Path = DEFAULT_LOCK_PATH,
    vision_image_max_width: int | None = None,
    scan_mode: str = "region",
) -> dict[str, Any]:
    """Verify only immutable inputs; never create an OCR worker or use the GPU."""
    lock = validate_benchmark_lock(PROJECT_ROOT, lock_path)
    if lock.get("ok") is not True:
        raise ValueError("benchmark lock validation failed")
    manifest = _load_manifest(manifest_path)
    cases = _locked_cases(manifest)
    _verify_images(cases)
    assets = resolve_preferred_vision_assets(PROJECT_ROOT)
    asset_hashes = _verify_assets(assets)
    baseline, candidate = build_conditions(
        assets,
        asset_hashes=asset_hashes,
        vision_image_max_width=vision_image_max_width,
        scan_mode=scan_mode,
    )
    return {"ok": True, "manifest": manifest, "assets": assets, "baseline": baseline, "candidate": candidate}


def _session_factory(timeout_seconds: int):
    return lambda: ProductPathLocalSession(OCRWorker, timeout_seconds=timeout_seconds)


def _with_runner_metadata(
    report: Mapping[str, Any], execution_order: str
) -> dict[str, Any]:
    result = dict(report)
    metadata = dict(result.get("metadata", {}))
    metadata.update({
        "execution_order": execution_order,
        "latency_order_balanced": False,
    })
    result["metadata"] = metadata
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Locked local Vision product-path benchmark")
    parser.add_argument("--manifest", required=True, help="locked owner-confirmed manifest JSON")
    parser.add_argument("--startup-timeout", type=int, default=30, help="local runtime startup timeout in seconds")
    parser.add_argument(
        "--vision-max-width",
        type=int,
        choices=range(640, 1537),
        help="optional controlled local Vision width experiment; default keeps product policy",
    )
    parser.add_argument(
        "--scan-mode",
        choices=("region", "fullscreen"),
        default="region",
        help="locked product scan mode; fullscreen explicitly evaluates Vision-first",
    )
    parser.add_argument(
        "--execution-order",
        choices=sorted(EXECUTION_ORDERS),
        default="baseline_then_candidate",
        help="condition order for this paired run; execute both orders for balanced latency evidence",
    )
    parser.add_argument("--preflight", action="store_true", help="validate immutable inputs without starting GPU runtime")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.startup_timeout < 1:
        raise ValueError("startup-timeout must be at least 1")
    try:
        preflight_kwargs = {}
        if args.vision_max_width is not None:
            preflight_kwargs["vision_image_max_width"] = args.vision_max_width
        if args.scan_mode != "region":
            preflight_kwargs["scan_mode"] = args.scan_mode
        ready = preflight(args.manifest, **preflight_kwargs)
        if args.preflight:
            print(json.dumps({"ok": True, "preflight": True}, separators=(",", ":")))
            return 0
        # Worker diagnostics may contain raw OCR content, so never emit them.
        with contextlib.redirect_stdout(io.StringIO()):
            report = evaluate_product_path_pair(
                ready["manifest"], ready["baseline"], ready["candidate"],
                worker_factory=OCRWorker,
                configure_worker=lambda _worker, _condition: None,
                image_loader=load_image,
                residual_probe=lambda _worker: 0,
                runtime_mode_probe=lambda _worker: "gpu",
                session_factory=_session_factory(args.startup_timeout),
                execution_order=args.execution_order,
            )
        print(json.dumps(
            redact_report(_with_runner_metadata(report, args.execution_order)),
            ensure_ascii=False,
            separators=(",", ":"),
        ))
        return 0
    except Exception as exc:
        safe_message = str(exc)
        if safe_message.startswith("scan trace rejected: "):
            print(
                f"benchmark_failed: {type(exc).__name__}: {safe_message}",
                file=sys.stderr,
            )
        else:
            print(f"benchmark_failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
