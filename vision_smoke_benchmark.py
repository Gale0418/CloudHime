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
    force_cpu: bool = False,
    small_image_scale: float = 1.0,
    prompt_mode: str = "baseline",
    model_name: str = DEFAULT_MODEL,
) -> dict[str, Any]:
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
    )
    startup_started = time.perf_counter()
    results: list[dict[str, Any]] = []
    image_results: list[dict[str, Any]] = []
    try:
        state = runtime.start()
        startup_ms = (time.perf_counter() - startup_started) * 1000.0
        if state.name != "ready":
            raise RuntimeError(f"local vision runtime failed: {state.detail}")

        provider = LocalMultimodalProvider(
            base_url=state.base_url,
            model_name=model_name,
            enabled=True,
            timeout_seconds=timeout_seconds,
        )
        for sample_source, image_cases in group_cases_by_image(cases).items():
            image_path = PROJECT_ROOT / sample_source
            request_started = time.perf_counter()
            error = ""
            actual = ""
            try:
                result = provider.transcribe_screenshot(
                    image_parts(image_path, small_image_scale=small_image_scale),
                    ocr_prompt=ocr_prompt,
                )
                actual = result.text.strip()
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = (time.perf_counter() - request_started) * 1000.0
            image_results.append(
                {
                    "sample_source": sample_source,
                    "categories": sorted({str(case.get("category", "")) for case in image_cases}),
                    "actual": actual,
                    "latency_ms": latency_ms,
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

    latencies = [float(result["latency_ms"]) for result in image_results]
    successful_cases = [result for result in results if result["actual"] and not result["error"]]
    successful_images = [result for result in image_results if result["actual"] and not result["error"]]
    runtime_mode = "cpu" if force_cpu else state.mode
    return {
        "manifest": str(manifest_path),
        "model": model_name,
        "runtime_mode": runtime_mode,
        "small_image_scale": max(1.0, float(small_image_scale)),
        "prompt_mode": prompt_mode,
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
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--small-image-scale", type=float, default=1.0)
    parser.add_argument("--prompt-mode", choices=tuple(OCR_PROMPTS), default="baseline")
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
        force_cpu=args.force_cpu,
        small_image_scale=args.small_image_scale,
        prompt_mode=args.prompt_mode,
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
        f"avg_latency_ms={result['average_latency_ms']:.1f} p95_latency_ms={result['p95_latency_ms']:.1f}"
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
