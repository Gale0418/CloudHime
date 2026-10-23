"""CH-T61 locked temporal holdout for frame policy, not OCR or model quality."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from benchmark_lock import load_lock, validate_benchmark_lock
from exact_image_cache import ExactImageCache
from frame_gate import FrameGate


PROJECT_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PROJECT_ROOT / "benchmarks" / "temporal_holdout_cases.json"
LOCK_PATH = PROJECT_ROOT / "benchmarks" / "benchmark_lock.json"
SEQUENCE_TRANSFORMS = (
    "blank_baseline",
    "source",
    "exact_repeat",
    "same_semantic_1px_noise",
    "blank",
    "single_frame_source",
    "blank",
)
_ALLOWED_CASE_FIELDS = {
    "category",
    "id",
    "note",
    "sequence_transforms",
    "source",
}
_PROHIBITED_CASE_FIELDS = {
    "actual",
    "expected",
    "ground_truth",
    "ocr",
    "visible_text_anchors",
}
_ALLOWED_CATEGORIES = {
    "owner_confirmed_example",
    "synthetic_adversarial",
    "user_provided_example",
}



def load_manifest(path: str | Path = MANIFEST_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("evaluation_scope") != "frame_policy_only":
        raise ValueError("temporal holdout must remain frame-policy-only")
    schema = payload.get("case_schema")
    if (
        not isinstance(schema, dict)
        or set(schema.get("fields", ())) != _ALLOWED_CASE_FIELDS
    ):
        raise ValueError("temporal holdout case schema fields are not locked")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("temporal holdout cases must be a non-empty list")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("temporal holdout case must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError("temporal holdout case ids must be unique and non-empty")
        case_ids.add(case_id)
        if _PROHIBITED_CASE_FIELDS.intersection(case):
            raise ValueError("temporal holdout must not carry OCR anchors or ground truth")
        if not set(case).issubset(_ALLOWED_CASE_FIELDS):
            raise ValueError("temporal holdout case contains an unknown field")
        if case.get("category") not in _ALLOWED_CATEGORIES:
            raise ValueError("temporal holdout category is not allowed")
        if tuple(case.get("sequence_transforms", ())) != SEQUENCE_TRANSFORMS:
            raise ValueError("temporal holdout sequence transforms are not locked")
        source = case.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError("temporal holdout source must be non-empty")
        if case["category"] != "synthetic_adversarial":
            relative = Path(source)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("temporal holdout source path must stay relative")
    return payload


def read_image_unicode_safe(path: str | Path) -> np.ndarray:
    """Decode image bytes so Windows paths with non-ASCII names stay valid."""
    encoded = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"image unreadable: {path}")
    return np.ascontiguousarray(image)


def _synthetic_source() -> np.ndarray:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[31, 31] = 96
    return image


def _blank_like(image: np.ndarray) -> np.ndarray:
    border = np.concatenate(
        (image[0], image[-1], image[:, 0], image[:, -1]), axis=0
    )
    color = np.median(border, axis=0).astype(image.dtype)
    return np.broadcast_to(color, image.shape).copy()


def _near_noise(image: np.ndarray) -> np.ndarray:
    noisy = image.copy()
    row = image.shape[0] - 1
    column = image.shape[1] - 1
    value = int(noisy[row, column, 0])
    noisy[row, column, 0] = np.uint8(value - 1 if value else 1)
    return noisy


def build_sequence(source: np.ndarray) -> tuple[tuple[str, np.ndarray, str], ...]:
    blank = _blank_like(source)
    return (
        ("blank_baseline", blank.copy(), "blank"),
        ("source", source.copy(), "source"),
        ("exact_repeat", source.copy(), "source"),
        ("same_semantic_1px_noise", _near_noise(source), "source"),
        ("blank", blank.copy(), "blank"),
        ("single_frame_source", source.copy(), "source"),
        ("blank", blank.copy(), "blank"),
    )


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.95
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _load_source(case: dict[str, Any]) -> np.ndarray:
    if case["category"] == "synthetic_adversarial":
        return _synthetic_source()
    root = PROJECT_ROOT.resolve()
    source = (root / case["source"]).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError("temporal holdout source escapes project root") from exc
    return read_image_unicode_safe(source)


def _run_policy(cases: list[dict[str, Any]], near_skip: bool) -> dict[str, Any]:
    gate_latencies: list[float] = []
    event_count = 0
    event_hits = 0
    single_count = 0
    single_hits = 0
    false_event_skips = 0
    exact_hits = 0
    processed = 0
    policy_skips = 0
    counterexamples: list[dict[str, str]] = []

    for case in cases:
        cache = ExactImageCache(max_entries=8, max_bytes=128 * 1024 * 1024)
        gate = FrameGate()
        previous_state: str | None = None
        for transform, frame, semantic_state in build_sequence(_load_source(case)):
            started = time.perf_counter_ns()
            observation = gate.observe(frame, context=case["id"])
            gate_latencies.append((time.perf_counter_ns() - started) / 1_000_000.0)
            exact_hit = cache.get(frame, case["id"]) is not None
            is_event = previous_state is not None and semantic_state != previous_state
            is_single = transform == "single_frame_source"
            near_policy_skip = (
                near_skip
                and not exact_hit
                and observation.classification in {"identical", "near"}
            )
            should_skip = exact_hit or near_policy_skip

            exact_hits += int(exact_hit)
            policy_skips += int(near_policy_skip)
            if is_event:
                event_count += 1
                single_count += int(is_single)
                if near_policy_skip:
                    false_event_skips += 1
                    counterexamples.append(
                        {
                            "case_id": case["id"],
                            "classification": observation.classification,
                            "transform": transform,
                        }
                    )
                else:
                    event_hits += 1
                    single_hits += int(is_single)

            if not should_skip:
                processed += 1
                if not cache.put(frame, case["id"], (semantic_state,), None, None):
                    raise RuntimeError("temporal holdout frame did not fit ExactImageCache")
            previous_state = semantic_state

    total_frames = len(cases) * len(SEQUENCE_TRANSFORMS)
    return {
        "event_recall": event_hits / event_count,
        "single_frame_recall": single_hits / single_count,
        "false_event_skips": false_event_skips,
        "exact_hits": exact_hits,
        "coverage": (processed + exact_hits) / total_frames,
        "processed_frames": processed,
        "policy_skips": policy_skips,
        "gate_p95_ms": _p95(gate_latencies),
        "counterexamples": counterexamples,
    }



def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _locked_manifest_hash(lock: dict[str, Any]) -> str:
    for dataset in lock.get("datasets", ()):
        if isinstance(dataset, dict) and dataset.get("id") == "temporal_holdout":
            value = dataset.get("sha256")
            if isinstance(value, str):
                return value.lower()
    raise RuntimeError("temporal holdout dataset is missing from benchmark lock")


def run_benchmark(manifest_path: str | Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest_file = Path(manifest_path).resolve()
    if manifest_file != MANIFEST_PATH.resolve():
        raise ValueError("temporal holdout runner only accepts the locked manifest")
    status = validate_benchmark_lock(PROJECT_ROOT, LOCK_PATH)
    if not status["ok"]:
        raise RuntimeError(f"benchmark lock validation failed: {status['errors']}")
    lock = load_lock(LOCK_PATH)
    locked_hash = _locked_manifest_hash(lock)
    actual_hash = _sha256_path(manifest_file)
    if actual_hash != locked_hash:
        raise RuntimeError("temporal holdout manifest hash does not match benchmark lock")
    manifest = load_manifest(manifest_file)
    safe = _run_policy(manifest["cases"], near_skip=False)
    hypothetical = _run_policy(manifest["cases"], near_skip=True)
    hard_gate_passed = (
        safe["false_event_skips"] == 0
        and safe["event_recall"] == 1.0
        and safe["single_frame_recall"] == 1.0
        and safe["coverage"] == 1.0
    )
    return {
        "benchmark": "CH-T61 locked temporal holdout",
        "evaluation_scope": "frame_policy_only",
        "not_an_ocr_or_model_benchmark": True,
        "sequence_transforms": list(SEQUENCE_TRANSFORMS),
        "case_count": len(manifest["cases"]),
        "safe_policy_hard_gate_passed": hard_gate_passed,
        "safe_exact_only_shadow_policy": safe,
        "hypothetical_near_skip_policy": hypothetical,
        "near_skip_counterexample": {
            "repeatable": bool(hypothetical["counterexamples"]),
            "reason": (
                "A non-exact semantic state transition is classified near or "
                "identical and would be skipped."
            ),
            "contains_text_ground_truth": False,
        },
        "benchmark_lock_id": lock["lock_id"],
        "manifest_hash": actual_hash,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CH-T61 temporal frame-policy holdout; not an OCR/model benchmark"
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)
    result = run_benchmark()
    if args.json:
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["safe_policy_hard_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
