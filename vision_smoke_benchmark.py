"""Run a repeatable local Gemma 3 image OCR smoke benchmark."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import time
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

import cv2
import numpy as np

from local_vision_assets import resolve_vision_assets
from local_vision_runtime import LocalVisionRuntime
from translation_providers import LocalMultimodalProvider


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PROJECT_ROOT / "benchmarks" / "ocr_accuracy_cases.json"
DEFAULT_MODEL = "gemma-3-4b-it"
OCR_PROMPTS = {
    "baseline": "You are an OCR engine. Read every visible line exactly as it appears. Return plain text only.",
    "strict_ocr": (
        "You are a meticulous OCR engine.\n"
        "Transcribe every visible text line exactly as it appears in the image.\n"
        "Do not translate, summarize, correct, complete, or infer text.\n"
        "Preserve the original line order, line breaks, punctuation, capitalization, Latin letters, "
        "and Japanese hiragana, katakana, and kanji.\n"
        "Copy uncertain characters as seen instead of substituting a likely word.\n"
        "Return plain OCR text only, with no explanation."
    ),
    "japanese_ocr": (
        "Read the Japanese text in this image exactly as shown. "
        "Preserve every hiragana, katakana, kanji, punctuation, and line break. "
        "Do not translate, correct, infer, or add text. Output only the original Japanese text."
    ),
}



def load_cases(manifest_path: str | Path, *, max_cases: int | None = None) -> list[dict[str, Any]]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    cases = [case for case in manifest.get("cases", []) if case.get("sample_source")]
    if max_cases is not None:
        cases = cases[: max(1, int(max_cases))]
    return cases


def normalize_for_match(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+", "", text)


def expected_variants(case: dict[str, Any]) -> list[str]:
    expected = case.get("expected", "")
    if isinstance(expected, list):
        return [str(item) for item in expected if str(item).strip()]
    return [str(expected)] if str(expected).strip() else []


def line_match(actual: str, case: dict[str, Any]) -> float:
    normalized_actual = normalize_for_match(actual)
    if not normalized_actual:
        return 0.0
    return float(
        any(
            normalize_for_match(expected) and normalize_for_match(expected) in normalized_actual
            for expected in expected_variants(case)
        )
    )


def score_match(actual: str, case: dict[str, Any]) -> float:
    normalized_actual = normalize_for_match(actual)
    if not normalized_actual:
        return 0.0
    if line_match(actual, case):
        return 1.0
    candidates = [normalized_actual]
    candidates.extend(normalize_for_match(line) for line in str(actual).splitlines())
    return max(
        (
            SequenceMatcher(None, normalize_for_match(expected), candidate).ratio()
            for expected in expected_variants(case)
            for candidate in candidates
        ),
        default=0.0,
    )


def image_parts(image_path: Path, *, small_image_scale: float = 1.0) -> list[dict[str, Any]]:
    image_bytes = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    mime_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    scale = max(1.0, float(small_image_scale))
    if scale > 1.0:
        decoded = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if decoded is not None and decoded.shape[0] < 160:
            resized = cv2.resize(
                decoded,
                (round(decoded.shape[1] * scale), round(decoded.shape[0] * scale)),
                interpolation=cv2.INTER_CUBIC,
            )
            success, encoded_image = cv2.imencode(".png", resized)
            if success:
                image_bytes = encoded_image.tobytes()
                mime_type = "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return [{"inline_data": {"mime_type": mime_type, "data": encoded}}]


def build_windows_ocr_hint(worker: Any, image_path: Path) -> str:
    if worker is None:
        return ""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return ""
    try:
        return str(worker.build_screenshot_text_hint(image) or "").strip()
    except Exception:
        return ""


def percentile(values: Sequence[float], quantile: float = 0.95) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, int(np.ceil(len(ordered) * quantile)) - 1))
    return ordered[index]


def group_cases_by_image(cases: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        grouped.setdefault(str(case["sample_source"]), []).append(case)
    return grouped


def run_smoke(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    *,
    max_cases: int = 5,
    timeout_seconds: int = 120,
    startup_timeout_seconds: int = 90,
    context_size: int = 4096,
    gpu_layers: int = 999,
    require_gpu: bool = False,
    force_cpu: bool = False,
    small_image_scale: float = 1.0,
    prompt_mode: str = "baseline",
    ocr_hint: bool = False,
    model_name: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    effective_gpu_layers = 0 if force_cpu else max(0, int(gpu_layers))
    if require_gpu and force_cpu:
        raise ValueError("require_gpu cannot be combined with force_cpu")
    if require_gpu and effective_gpu_layers <= 0:
        raise ValueError("require_gpu needs gpu_layers > 0")

    cases = load_cases(manifest_path, max_cases=max_cases)
    if not cases:
        raise ValueError("vision smoke benchmark needs at least one sample_source case")
    try:
        ocr_prompt = OCR_PROMPTS[prompt_mode]
    except KeyError as exc:
        raise ValueError(f"unknown prompt mode: {prompt_mode}") from exc

    popen_factory = subprocess.Popen
    if force_cpu:
        def popen_cpu(command: Sequence[str], **kwargs: Any):
            command = list(command)
            ngl_index = command.index("-ngl")
            command[ngl_index + 1] = "0"
            return subprocess.Popen(command, **kwargs)

        popen_factory = popen_cpu

    runtime = LocalVisionRuntime(
        resolve_vision_assets(PROJECT_ROOT),
        popen_factory=popen_factory,
        health_retries=max(1, int(startup_timeout_seconds * 2)),
        context_size=max(512, int(context_size)),
        gpu_layers=effective_gpu_layers,
    )
    startup_started = time.perf_counter()
    results: list[dict[str, Any]] = []
    image_results: list[dict[str, Any]] = []
    ocr_hint_worker = None
    try:
        state = runtime.start()
        startup_ms = (time.perf_counter() - startup_started) * 1000.0
        if state.name != "ready":
            raise RuntimeError(f"local vision runtime failed: {state.detail}")
        if require_gpu and state.mode != "gpu":
            raise RuntimeError(f"gpu_required_but_runtime_mode={state.mode}")

        provider = LocalMultimodalProvider(
            base_url=state.base_url,
            model_name=model_name,
            enabled=True,
            timeout_seconds=timeout_seconds,
        )
        if ocr_hint:
            from cloudhime_workers import OCRWorker
            ocr_hint_worker = OCRWorker()
            ocr_hint_worker.reload_ocr_backends(["windows"], log=False)
        for sample_source, image_cases in group_cases_by_image(cases).items():
            image_path = PROJECT_ROOT / sample_source
            request_started = time.perf_counter()
            error = ""
            actual = ""
            ocr_hint_text = ""
            hint_ms = 0.0
            image_encode_ms = 0.0
            model_request_ms = 0.0
            postprocess_ms = 0.0
            try:
                stage_started = time.perf_counter()
                try:
                    ocr_hint_text = build_windows_ocr_hint(ocr_hint_worker, image_path)
                finally:
                    hint_ms = (time.perf_counter() - stage_started) * 1000.0

                stage_started = time.perf_counter()
                try:
                    parts = image_parts(image_path, small_image_scale=small_image_scale)
                finally:
                    image_encode_ms = (time.perf_counter() - stage_started) * 1000.0

                stage_started = time.perf_counter()
                try:
                    result = provider.transcribe_screenshot(
                        parts,
                        ocr_prompt=ocr_prompt,
                        source_text_hint=ocr_hint_text,
                    )
                finally:
                    model_request_ms = (time.perf_counter() - stage_started) * 1000.0

                stage_started = time.perf_counter()
                try:
                    actual = result.text.strip()
                finally:
                    postprocess_ms = (time.perf_counter() - stage_started) * 1000.0
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = (time.perf_counter() - request_started) * 1000.0
            image_results.append(
                {
                    "sample_source": sample_source,
                    "categories": sorted({str(case.get("category", "")) for case in image_cases}),
                    "actual": actual,
                    "latency_ms": latency_ms,
                    "hint_ms": hint_ms,
                    "image_encode_ms": image_encode_ms,
                    "model_request_ms": model_request_ms,
                    "postprocess_ms": postprocess_ms,
                    "ocr_hint": ocr_hint_text,
                    "error": error,
                }
            )
            for case in image_cases:
                results.append(
                    {
                        "category": case.get("category", ""),
                        "sample_source": sample_source,
                        "expected": expected_variants(case),
                        "actual": actual,
                        "line_match": line_match(actual, case),
                        "match_score": score_match(actual, case),
                        "latency_ms": latency_ms,
                        "error": error,
                    }
                )
    finally:
        runtime.stop()
        if ocr_hint_worker is not None:
            ocr_hint_worker.cleanup()
    latencies = [float(result["latency_ms"]) for result in image_results]
    hint_latencies = [float(result["hint_ms"]) for result in image_results]
    encode_latencies = [float(result["image_encode_ms"]) for result in image_results]
    model_latencies = [float(result["model_request_ms"]) for result in image_results]
    postprocess_latencies = [float(result["postprocess_ms"]) for result in image_results]
    successful_cases = [result for result in results if result["actual"] and not result["error"]]
    successful_images = [result for result in image_results if result["actual"] and not result["error"]]
    runtime_mode = "cpu" if force_cpu else state.mode
    return {
        "manifest": str(manifest_path),
        "model": model_name,
        "runtime_mode": runtime_mode,
        "gpu_layers": effective_gpu_layers,
        "require_gpu": bool(require_gpu),
        "small_image_scale": max(1.0, float(small_image_scale)),
        "prompt_mode": prompt_mode,
        "ocr_hint": bool(ocr_hint),
        "startup_ms": startup_ms,
        "image_count": len(image_results),
        "case_count": len(results),
        "successful_images": len(successful_images),
        "successful_cases": len(successful_cases),
        "line_match_cases": sum(float(result["line_match"]) for result in results),
        "average_line_match": mean(float(result["line_match"]) for result in results),
        "average_match_score": mean(float(result["match_score"]) for result in results),
        "average_latency_ms": mean(latencies),
        "p95_latency_ms": percentile(latencies),
        "average_hint_ms": mean(hint_latencies),
        "average_image_encode_ms": mean(encode_latencies),
        "average_model_request_ms": mean(model_latencies),
        "p95_model_request_ms": percentile(model_latencies),
        "average_postprocess_ms": mean(postprocess_latencies),
        "image_results": image_results,
        "results": results,
    }

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CloudHime local Gemma 3 image OCR smoke benchmark")
    parser.add_argument("manifest", nargs="?", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--startup-timeout", type=int, default=90)
    parser.add_argument("--context-size", type=int, default=4096)
    parser.add_argument("--gpu-layers", type=int, default=999)
    parser.add_argument("--require-gpu", action="store_true")
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--small-image-scale", type=float, default=1.0)
    parser.add_argument("--prompt-mode", choices=tuple(OCR_PROMPTS), default="baseline")
    parser.add_argument("--ocr-hint", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(
        args.manifest,
        max_cases=args.max_cases,
        timeout_seconds=args.timeout,
        startup_timeout_seconds=args.startup_timeout,
        context_size=args.context_size,
        gpu_layers=args.gpu_layers,
        require_gpu=args.require_gpu,
        force_cpu=args.force_cpu,
        small_image_scale=args.small_image_scale,
        prompt_mode=args.prompt_mode,
        ocr_hint=args.ocr_hint,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(
        "Vision Smoke Summary: "
        f"mode={result['runtime_mode']} images={result['image_count']} cases={result['case_count']} "
        f"success={result['successful_cases']} startup_ms={result['startup_ms']:.1f} "
        f"line_match={result['line_match_cases']:.0f}/{result['case_count']} "
        f"scale={result['small_image_scale']:.1f} "
        f"prompt={result['prompt_mode']} "
        f"avg_match={result['average_match_score']:.3f} "
        f"avg_latency_ms={result['average_latency_ms']:.1f} p95_latency_ms={result['p95_latency_ms']:.1f} "
        f"stages_ms=hint:{result['average_hint_ms']:.1f},encode:{result['average_image_encode_ms']:.1f},"
        f"model:{result['average_model_request_ms']:.1f},post:{result['average_postprocess_ms']:.1f}"
    )
    for item in result["results"]:
        print(
            f"- category={item['category']} source={item['sample_source']} "
            f"line_match={item['line_match']:.0f} match={item['match_score']:.3f} "
            f"latency_ms={item['latency_ms']:.1f} actual={item['actual'] or item['error']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
