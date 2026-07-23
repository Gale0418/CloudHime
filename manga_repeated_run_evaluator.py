"""Paired repeated-run OCR evaluator for manga accuracy and latency."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import cv2

import fullscreen_manga_benchmark as fullscreen_benchmark


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_ALLOWLIST = (
    "CLOUDHIME_MANGA_CROP_CONTEXT",
    "CLOUDHIME_MANGA_GRID_RECOVERY",
    "CUDA_VISIBLE_DEVICES",
    "OMP_NUM_THREADS",
    "PYTHONHASHSEED",
)


def _read_json(path: str | Path) -> Mapping[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(
        char
        for char in unicodedata.normalize("NFKC", value).casefold()
        if not char.isspace()
    )


def _image_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_image(manifest_path: Path, image: str) -> Path:
    candidate = Path(image)
    if candidate.is_absolute():
        return candidate.resolve()
    for root in (PROJECT_ROOT, manifest_path.parent):
        resolved = (root / candidate).resolve()
        if resolved.exists():
            return resolved
    return (PROJECT_ROOT / candidate).resolve()


def load_suite(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path).resolve()
    manifest = _read_json(manifest_path)
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain a non-empty cases list")

    normalized_cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_images: set[str] = set()
    for index, raw in enumerate(cases):
        if not isinstance(raw, Mapping):
            raise ValueError(f"case at index {index} must be an object")
        image = raw.get("image")
        if not isinstance(image, str) or not image.strip():
            raise ValueError(f"case at index {index} needs a non-empty image")
        image = image.strip()
        case_id = str(raw.get("id") or image).strip()
        if not case_id or case_id in seen_ids:
            raise ValueError(f"duplicate or empty case id: {case_id!r}")
        image_key = image.replace("\\", "/")
        if image_key in seen_images:
            raise ValueError(f"duplicate image: {image}")
        seen_ids.add(case_id)
        seen_images.add(image_key)

        anchors = raw.get("anchors", raw.get("visible_text_anchors", []))
        if not isinstance(anchors, list):
            raise ValueError(f"case {case_id!r} anchors must be a list")
        clean_anchors = []
        normalized_anchors: set[str] = set()
        for anchor in anchors:
            if not isinstance(anchor, str) or not anchor.strip():
                raise ValueError(f"case {case_id!r} has an invalid anchor")
            anchor = anchor.strip()
            normalized_anchor = _normalize_text(anchor)
            if normalized_anchor in normalized_anchors:
                raise ValueError(f"case {case_id!r} has duplicate anchors")
            normalized_anchors.add(normalized_anchor)
            clean_anchors.append(anchor)

        image_path = _resolve_image(manifest_path, image)
        if not image_path.is_file():
            raise FileNotFoundError(f"case {case_id!r} image not found: {image}")
        normalized_cases.append(
            {
                "id": case_id,
                "image": image,
                "path": image_path,
                "anchors": clean_anchors,
                "image_sha256": _image_sha256(image_path),
            }
        )

    return {
        "name": manifest_path.name,
        "path": manifest_path,
        "manifest_sha256": _image_sha256(manifest_path),
        "cases": normalized_cases,
    }


def percentile(values: Iterable[float], quantile: float = 0.95) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    rank = max(1, math.ceil(len(ordered) * quantile))
    return ordered[min(rank, len(ordered)) - 1]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _score_case(
    case: Mapping[str, Any],
    image_result: Mapping[str, Any],
    *,
    repeat: int,
    condition: str,
) -> dict[str, Any]:
    joined_text = _normalize_text(image_result.get("joined_text", ""))
    anchors = list(case["anchors"])
    hits = sum(_normalize_text(anchor) in joined_text for anchor in anchors)
    error = str(image_result.get("error", "") or "")
    return {
        "case_id": case["id"],
        "repeat": repeat,
        "condition": condition,
        "image_sha256": case["image_sha256"],
        "anchor_hits": hits,
        "anchor_count": len(anchors),
        "anchor_recall": hits / len(anchors) if anchors else None,
        "item_count": int(_number(image_result.get("item_count"), 0)),
        "elapsed_ms": _number(image_result.get("elapsed_ms"), 0.0),
        "error": error,
        "grid_recovery_triggered": bool(
            image_result.get("grid_recovery_triggered", False)
        ),
        "grid_recovery_accepted": bool(
            image_result.get("grid_recovery_accepted", False)
        ),
    }


def summarize_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total_anchors = sum(int(record["anchor_count"]) for record in records)
    hit_anchors = sum(int(record["anchor_hits"]) for record in records)
    page_recalls = [
        float(record["anchor_recall"])
        for record in records
        if record["anchor_recall"] is not None
    ]
    successful = [record for record in records if not record["error"]]
    latencies = [_number(record["elapsed_ms"]) for record in successful]
    nonempty = sum(int(record["item_count"]) > 0 for record in successful)

    return {
        "run_count": len(records),
        "successful_pages": len(successful),
        "nonempty_page_rate": nonempty / len(successful) if successful else None,
        "anchor_hits": hit_anchors,
        "anchor_count": total_anchors,
        "anchor_recall": hit_anchors / total_anchors if total_anchors else None,
        "page_macro_recall": (
            sum(page_recalls) / len(page_recalls) if page_recalls else None
        ),
        "item_count_avg": (
            sum(int(record["item_count"]) for record in successful) / len(successful)
            if successful
            else None
        ),
        "latency_ms": {
            "avg": sum(latencies) / len(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "p95": percentile(latencies),
            "count": len(latencies),
        },
        "grid_recovery_triggered": sum(
            bool(record["grid_recovery_triggered"]) for record in records
        ),
        "grid_recovery_accepted": sum(
            bool(record["grid_recovery_accepted"]) for record in records
        ),
    }


def compare_conditions(
    baseline: Sequence[Mapping[str, Any]],
    variant: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    baseline_summary = summarize_records(baseline)
    variant_summary = summarize_records(variant)

    def record_key(record: Mapping[str, Any]) -> tuple[str, int]:
        return (
            str(record["case_id"]),
            int(record.get("repeat", 1)),
        )

    baseline_map = {record_key(record): record for record in baseline}
    variant_map = {record_key(record): record for record in variant}
    common_keys = sorted(set(baseline_map) & set(variant_map))
    pair_deltas: list[dict[str, Any]] = []
    for key in common_keys:
        left = baseline_map[key]
        right = variant_map[key]
        if left["anchor_recall"] is None or right["anchor_recall"] is None:
            continue
        pair_deltas.append(
            {
                "case_id": key[0],
                "repeat": key[1],
                "baseline_recall": float(left["anchor_recall"]),
                "variant_recall": float(right["anchor_recall"]),
                "delta": float(right["anchor_recall"])
                - float(left["anchor_recall"]),
            }
        )

    case_deltas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for delta in pair_deltas:
        case_deltas[delta["case_id"]].append(delta)

    improved = equal = regressed = 0
    page_deltas: list[dict[str, Any]] = []
    for case_id in sorted(case_deltas):
        observations = case_deltas[case_id]
        base_score = sum(
            item["baseline_recall"] for item in observations
        ) / len(observations)
        variant_score = sum(
            item["variant_recall"] for item in observations
        ) / len(observations)
        delta = variant_score - base_score
        if delta > 1e-12:
            improved += 1
        elif delta < -1e-12:
            regressed += 1
        else:
            equal += 1
        page_deltas.append(
            {
                "case_id": case_id,
                "baseline_recall": base_score,
                "variant_recall": variant_score,
                "delta": delta,
                "repeat_count": len(observations),
                "regressed_repeats": sum(
                    item["delta"] < -1e-12 for item in observations
                ),
            }
        )

    repeat_deltas: list[dict[str, Any]] = []
    repeat_ids = sorted(
        {
            int(record.get("repeat", 1))
            for record in baseline
        }
        | {
            int(record.get("repeat", 1))
            for record in variant
        }
    )
    for repeat in repeat_ids:
        left_records = [
            record
            for record in baseline
            if int(record.get("repeat", 1)) == repeat
        ]
        right_records = [
            record
            for record in variant
            if int(record.get("repeat", 1)) == repeat
        ]
        left_summary = summarize_records(left_records)
        right_summary = summarize_records(right_records)
        observations = [
            item
            for item in pair_deltas
            if item["repeat"] == repeat
        ]
        repeat_deltas.append(
            {
                "repeat": repeat,
                "baseline_anchor_recall": left_summary["anchor_recall"],
                "variant_anchor_recall": right_summary["anchor_recall"],
                "anchor_delta": (
                    right_summary["anchor_recall"]
                    - left_summary["anchor_recall"]
                    if left_summary["anchor_recall"] is not None
                    and right_summary["anchor_recall"] is not None
                    else None
                ),
                "baseline_page_macro_recall": left_summary["page_macro_recall"],
                "variant_page_macro_recall": right_summary["page_macro_recall"],
                "page_macro_delta": (
                    right_summary["page_macro_recall"]
                    - left_summary["page_macro_recall"]
                    if left_summary["page_macro_recall"] is not None
                    and right_summary["page_macro_recall"] is not None
                    else None
                ),
                "page_regression": {
                    "improved_pages": sum(
                        item["delta"] > 1e-12 for item in observations
                    ),
                    "equal_pages": sum(
                        abs(item["delta"]) <= 1e-12 for item in observations
                    ),
                    "regressed_pages": sum(
                        item["delta"] < -1e-12 for item in observations
                    ),
                    "compared_pages": len(observations),
                },
            }
        )

    base_latency = baseline_summary["latency_ms"]
    variant_latency = variant_summary["latency_ms"]
    paired_regressions = sum(
        item["delta"] < -1e-12 for item in pair_deltas
    )
    return {
        "anchor_recall": {
            "baseline": baseline_summary["anchor_recall"],
            "variant": variant_summary["anchor_recall"],
            "delta": (
                variant_summary["anchor_recall"] - baseline_summary["anchor_recall"]
                if baseline_summary["anchor_recall"] is not None
                and variant_summary["anchor_recall"] is not None
                else None
            ),
        },
        "page_macro_recall": {
            "baseline": baseline_summary["page_macro_recall"],
            "variant": variant_summary["page_macro_recall"],
            "delta": (
                variant_summary["page_macro_recall"]
                - baseline_summary["page_macro_recall"]
                if baseline_summary["page_macro_recall"] is not None
                and variant_summary["page_macro_recall"] is not None
                else None
            ),
        },
        "page_regression": {
            "improved_pages": improved,
            "equal_pages": equal,
            "regressed_pages": regressed,
            "compared_pages": len(page_deltas),
        },
        "paired_repeat_regression": {
            "improved_observations": sum(
                item["delta"] > 1e-12 for item in pair_deltas
            ),
            "equal_observations": sum(
                abs(item["delta"]) <= 1e-12 for item in pair_deltas
            ),
            "regressed_observations": paired_regressions,
            "compared_observations": len(pair_deltas),
            "repeats_with_regression": sum(
                item["page_regression"]["regressed_pages"] > 0
                for item in repeat_deltas
            ),
            "repeats_without_regression": sum(
                item["page_regression"]["regressed_pages"] == 0
                for item in repeat_deltas
            ),
        },
        "latency_ms": {
            "baseline_avg": base_latency["avg"],
            "variant_avg": variant_latency["avg"],
            "avg_delta": (
                variant_latency["avg"] - base_latency["avg"]
                if base_latency["avg"] is not None and variant_latency["avg"] is not None
                else None
            ),
            "baseline_median": base_latency["median"],
            "variant_median": variant_latency["median"],
            "p95_delta": (
                variant_latency["p95"] - base_latency["p95"]
                if base_latency["p95"] is not None and variant_latency["p95"] is not None
                else None
            ),
            "baseline_p95": base_latency["p95"],
            "variant_p95": variant_latency["p95"],
        },
        "page_deltas": page_deltas,
        "repeat_deltas": repeat_deltas,
    }

def _git_value(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _metadata(backend_chain: Sequence[str], base_threshold: int) -> dict[str, Any]:
    return {
        "git_commit": _git_value("rev-parse", "HEAD"),
        "tracked_worktree_dirty": bool(
            _git_value("status", "--porcelain", "--untracked-files=no")
        ),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "opencv": cv2.__version__,
        "backend_chain": list(backend_chain),
        "base_threshold": int(base_threshold),
        "ocr_only": True,
        "multimodal_enabled": False,
        "environment": {
            name: os.environ.get(name)
            for name in ENV_ALLOWLIST
            if os.environ.get(name) is not None
        },
    }


def run_repeated_benchmark(
    manifest_path: str | Path,
    *,
    backend_chain: Sequence[str] | None = None,
    repeats: int = 1,
    base_threshold: int = 100,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    suite = load_suite(manifest_path)
    chain = fullscreen_benchmark._parse_backend_chain(backend_chain)
    cases = suite["cases"]
    image_paths = [case["path"] for case in cases]
    records: list[dict[str, Any]] = []

    for repeat in range(1, repeats + 1):
        conditions = ("baseline", "grid_recovery")
        if repeat % 2 == 0:
            conditions = tuple(reversed(conditions))
        for condition in conditions:
            payload = fullscreen_benchmark.run_benchmark(
                image_paths,
                backend_chain=chain,
                grid_recovery=condition == "grid_recovery",
                base_threshold=base_threshold,
            )
            images = payload.get("images", [])
            if len(images) != len(cases):
                raise RuntimeError(
                    f"benchmark returned {len(images)} images for {len(cases)} cases"
                )
            records.extend(
                _score_case(
                    case,
                    image_result,
                    repeat=repeat,
                    condition=condition,
                )
                for case, image_result in zip(cases, images)
            )

    baseline = [record for record in records if record["condition"] == "baseline"]
    variant = [
        record for record in records if record["condition"] == "grid_recovery"
    ]
    return {
        "schema_version": 1,
        "metadata": _metadata(chain, base_threshold),
        "suite": {
            "name": suite["name"],
            "manifest_sha256": suite["manifest_sha256"],
            "case_count": len(cases),
            "anchor_count": sum(len(case["anchors"]) for case in cases),
            "image_sha256": {
                case["id"]: case["image_sha256"] for case in cases
            },
        },
        "conditions": {
            "baseline": summarize_records(baseline),
            "grid_recovery": summarize_records(variant),
        },
        "comparison": compare_conditions(baseline, variant),
        "records": records,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CloudHime 漫畫 OCR paired repeated-run evaluator"
    )
    parser.add_argument("manifest", help="私有 annotation 或公開 holdout manifest")
    parser.add_argument(
        "--backend",
        action="append",
        dest="backend_chain",
        help="OCR backend chain；可重複指定或用逗號分隔",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="baseline/grid 配對重複次數，建議正式測試至少 5",
    )
    parser.add_argument(
        "--base-threshold",
        type=int,
        default=100,
        help="每頁開始時重設的基準 threshold",
    )
    parser.add_argument("--output", help="將不含 OCR 原文的摘要報告寫入 JSON")
    parser.add_argument("--pretty", action="store_true", help="美化 JSON 輸出")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_repeated_benchmark(
            args.manifest,
            backend_chain=args.backend_chain,
            repeats=args.repeats,
            base_threshold=args.base_threshold,
        )
    except Exception as exc:
        print(f"benchmark failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(
        report,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())