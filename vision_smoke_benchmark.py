"""Run a repeatable local Gemma 3 image OCR smoke benchmark."""

from __future__ import annotations

import argparse
import base64
import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

from local_vision_assets import resolve_vision_assets
from local_vision_runtime import LocalVisionRuntime
from translation_providers import LocalMultimodalProvider


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PROJECT_ROOT / "benchmarks" / "ocr_accuracy_cases.json"
DEFAULT_MODEL = "gemma-3-4b-it"


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


def score_match(actual: str, case: dict[str, Any]) -> float:
    normalized_actual = normalize_for_match(actual)
    if not normalized_actual:
        return 0.0
    return max(
        (SequenceMatcher(None, normalize_for_match(expected), normalized_actual).ratio() for expected in expected_variants(case)),
        default=0.0,
    )


def image_parts(image_path: Path) -> list[dict[str, Any]]:
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    suffix = image_path.suffix.lower()
    mime_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    return [{"inline_data": {"mime_type": mime_type, "data": encoded}}]


def run_smoke(
    manifest_path: str | Path = DEFAULT_MANIFEST,
    *,
    max_cases: int = 5,
    timeout_seconds: int = 120,
    model_name: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    cases = load_cases(manifest_path, max_cases=max_cases)
    if not cases:
        raise ValueError("vision smoke benchmark needs at least one sample_source case")

    runtime = LocalVisionRuntime(resolve_vision_assets(PROJECT_ROOT))
    startup_started = time.perf_counter()
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
    results: list[dict[str, Any]] = []
    try:
        for case in cases:
            image_path = PROJECT_ROOT / str(case["sample_source"])
            request_started = time.perf_counter()
            error = ""
            actual = ""
            try:
                result = provider.transcribe_screenshot(image_parts(image_path))
                actual = result.text.strip()
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = (time.perf_counter() - request_started) * 1000.0
            results.append(
                {
                    "category": case.get("category", ""),
                    "sample_source": str(case["sample_source"]),
                    "expected": expected_variants(case),
                    "actual": actual,
                    "match_score": score_match(actual, case),
                    "latency_ms": latency_ms,
                    "error": error,
                }
            )
    finally:
        runtime.stop()

    latencies = [float(result["latency_ms"]) for result in results]
    successful = [result for result in results if result["actual"] and not result["error"]]
    return {
        "manifest": str(manifest_path),
        "model": model_name,
        "runtime_mode": state.mode,
        "startup_ms": startup_ms,
        "case_count": len(results),
        "successful_cases": len(successful),
        "average_match_score": mean(float(result["match_score"]) for result in results),
        "average_latency_ms": mean(latencies),
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CloudHime local Gemma 3 image OCR smoke benchmark")
    parser.add_argument("manifest", nargs="?", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--max-cases", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_smoke(args.manifest, max_cases=args.max_cases, timeout_seconds=args.timeout)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(
        "Vision Smoke Summary: "
        f"mode={result['runtime_mode']} cases={result['case_count']} "
        f"success={result['successful_cases']} startup_ms={result['startup_ms']:.1f} "
        f"avg_match={result['average_match_score']:.3f} "
        f"avg_latency_ms={result['average_latency_ms']:.1f}"
    )
    for item in result["results"]:
        print(
            f"- category={item['category']} source={item['sample_source']} "
            f"match={item['match_score']:.3f} latency_ms={item['latency_ms']:.1f} "
            f"actual={item['actual'] or item['error']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
