"""Model-free source-disjoint OCR/translation benchmark evaluator."""
from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PROJECT_ROOT / "benchmarks" / "translation_e2e_cases.json"
VALID_SPLITS = frozenset({"train", "dev", "test"})
LATENCY_STAGES = (
    "capture",
    "ocr",
    "translation",
    "encode",
    "runtime",
    "model",
    "fallback",
    "total",
)
QUALITY_WEIGHTS = {
    "translation_char_score": 0.65,
    "required_terms_recall": 0.20,
    "ocr_char_similarity": 0.15,
}
CASE_FIELDS = (
    "id", "source_group", "image", "split", "source_lang", "target_lang",
    "reference_source", "reference_translations", "required_terms",
)


def _read_json(path: str | Path) -> Any:
    if str(path) == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _text(value: Any, field: str, case_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"case {case_id!r} field {field!r} must be a non-empty string")
    return value.strip()


def _text_list(
    value: Any,
    field: str,
    case_id: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        qualifier = "a string list" if allow_empty else "a non-empty string list"
        raise ValueError(f"case {case_id!r} field {field!r} must be {qualifier}")
    return [item.strip() for item in value]


def validate_manifest(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate the manifest and enforce source-group split disjointness."""
    if not isinstance(manifest, Mapping) or not isinstance(manifest.get("cases"), list):
        raise ValueError("manifest must be an object with a cases list")
    if not manifest["cases"]:
        raise ValueError("manifest cases list must not be empty")
    seen_ids: set[str] = set()
    group_splits: dict[str, str] = {}
    image_splits: dict[str, str] = {}
    validated = []
    for index, raw in enumerate(manifest["cases"]):
        if not isinstance(raw, Mapping):
            raise ValueError(f"case at index {index} must be an object")
        case_id = raw.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"case at index {index} needs a non-empty id")
        case_id = case_id.strip()
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)
        missing = [field for field in CASE_FIELDS if field not in raw]
        if missing:
            raise ValueError(f"case {case_id!r} missing required fields: {', '.join(missing)}")
        group = _text(raw["source_group"], "source_group", case_id)
        image = _text(raw["image"], "image", case_id)
        split = _text(raw["split"], "split", case_id).lower()
        if split not in VALID_SPLITS:
            raise ValueError(f"case {case_id!r} has invalid split {split!r}")
        normalized_fields = {
            field: _text(raw[field], field, case_id)
            for field in ("source_lang", "target_lang", "reference_source")
        }
        translations = _text_list(raw["reference_translations"], "reference_translations", case_id)
        terms = _text_list(raw["required_terms"], "required_terms", case_id, allow_empty=True)
        old_split = group_splits.setdefault(group, split)
        if old_split != split:
            raise ValueError(
                f"source_group {group!r} crosses splits: {old_split!r} and {split!r}"
            )
        old_image_split = image_splits.setdefault(image, split)
        if old_image_split != split:
            raise ValueError(
                f"image {image!r} crosses splits: {old_image_split!r} and {split!r}"
            )
        validated.append({
            **dict(raw),
            "id": case_id,
            "source_group": group,
            "image": image,
            "split": split,
            **normalized_fields,
            "reference_translations": translations,
            "required_terms": terms,
        })
    return validated


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest = _read_json(path)
    validate_manifest(manifest)
    return dict(manifest)


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    return validate_manifest(load_manifest(path))


def _prediction_items(payload: Any) -> list[Mapping[str, Any]]:
    sequence_types = (str, bytes, bytearray)
    if isinstance(payload, Sequence) and not isinstance(payload, sequence_types):
        items = payload
    elif isinstance(payload, Mapping):
        nested = payload.get("predictions")
        if not isinstance(nested, Sequence) or isinstance(nested, sequence_types):
            raise ValueError("predictions JSON must be a list or an object with predictions")
        items = nested
    else:
        raise ValueError("predictions JSON must be a list or an object with predictions")
    if any(not isinstance(item, Mapping) for item in items):
        raise ValueError("every prediction must be an object")
    return list(items)


def load_prediction_records(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    normalized = []
    for index, raw in enumerate(items):
        if not isinstance(raw, Mapping):
            raise ValueError(f"prediction at index {index} must be an object")
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"prediction at index {index} needs case_id")
        case_id = case_id.strip()
        if case_id in seen:
            raise ValueError(f"duplicate prediction case_id: {case_id}")
        seen.add(case_id)
        stages = raw.get("stages_ms")
        if stages is None:
            stages = {}
        if not isinstance(stages, Mapping):
            raise ValueError(f"prediction {case_id!r} stages_ms must be an object")
        clean_stages: dict[str, float] = {}
        for stage, value in stages.items():
            if not isinstance(stage, str) or not stage.strip() or isinstance(value, bool):
                raise ValueError(f"prediction {case_id!r} has an invalid stage")
            stage = stage.strip()
            if stage in clean_stages:
                raise ValueError(f"prediction {case_id!r} has conflicting stages")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"prediction {case_id!r} stage {stage!r} must be numeric") from exc
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"prediction {case_id!r} stage {stage!r} must be finite and >= 0")
            clean_stages[stage] = number
        normalized.append({**dict(raw), "case_id": case_id, "stages_ms": clean_stages})
    return normalized


def load_predictions(path: str | Path) -> list[dict[str, Any]]:
    return load_prediction_records(_prediction_items(_read_json(path)))


def _score_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(
        char for char in unicodedata.normalize("NFC", value).casefold()
        if not char.isspace()
    )


def _levenshtein(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, 1):
        current = [i]
        for j, right_char in enumerate(right, 1):
            current.append(min(
                current[-1] + 1, previous[j] + 1,
                previous[j - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def character_error_rate(actual: str, reference: str) -> float:
    actual_text, reference_text = _score_text(actual), _score_text(reference)
    if not reference_text:
        return 0.0 if not actual_text else 1.0
    return _levenshtein(actual_text, reference_text) / len(reference_text)


def character_similarity(actual: str, reference: str) -> float:
    actual_text, reference_text = _score_text(actual), _score_text(reference)
    if not actual_text and not reference_text:
        return 1.0
    return max(
        0.0,
        1.0 - _levenshtein(actual_text, reference_text)
        / max(len(actual_text), len(reference_text)),
    )


def translation_character_score(actual: str, references: Iterable[str]) -> float:
    candidates = [ref for ref in references if isinstance(ref, str) and ref.strip()]
    return max((character_similarity(actual, ref) for ref in candidates), default=0.0)


def required_terms_recall(actual: str, required_terms: Iterable[str]) -> float:
    terms = [term for term in required_terms if isinstance(term, str) and term.strip()]
    if not terms:
        return 1.0
    actual_text = _score_text(actual)
    return sum(_score_text(term) in actual_text for term in terms) / len(terms)


def percentile(values: Sequence[float], quantile: float = 0.95) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    rank = max(1, math.ceil(len(ordered) * quantile))
    return ordered[min(rank, len(ordered)) - 1]


def _summary(values: Iterable[float], total: int) -> dict[str, Any]:
    values = [float(value) for value in values]
    return {
        "avg": sum(values) / len(values) if values else None,
        "p95": percentile(values),
        "coverage": len(values) / total if total else 0.0,
        "count": len(values),
        "total_cases": total,
    }


def _accuracy(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fields = ("ocr_char_similarity", "ocr_cer", "translation_char_score", "required_terms_recall")
    return {
        field: _summary(
            (record[field] for record in records if record[field] is not None),
            len(records),
        )
        for field in fields
    }


def _latency(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        stage: _summary(
            (record["stages_ms"][stage] for record in records if stage in record["stages_ms"]),
            len(records),
        )
        for stage in LATENCY_STAGES
    }


def _evaluate_cases(
    cases: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_case = {str(case["id"]): case for case in cases}
    by_prediction = {str(pred["case_id"]): pred for pred in predictions}
    unknown = sorted(set(by_prediction) - set(by_case))
    if unknown:
        raise ValueError(f"predictions contain unknown case_id(s): {', '.join(unknown)}")
    records = []
    for case in cases:
        prediction = by_prediction.get(str(case["id"]))
        source = prediction.get("detected_source") if prediction else None
        translation = prediction.get("translation") if prediction else None
        source_ok = isinstance(source, str) and bool(source.strip())
        translation_ok = isinstance(translation, str) and bool(translation.strip())
        ocr_cer = character_error_rate(source, case["reference_source"]) if source_ok else None
        ocr_similarity = (
            character_similarity(source, case["reference_source"]) if source_ok else None
        )
        translation_score = (
            translation_character_score(translation, case["reference_translations"])
            if translation_ok else None
        )
        terms_recall = (
            required_terms_recall(translation, case["required_terms"])
            if translation_ok else None
        )
        quality_score = (
            QUALITY_WEIGHTS["translation_char_score"] * (translation_score or 0.0)
            + QUALITY_WEIGHTS["required_terms_recall"] * (terms_recall or 0.0)
            + QUALITY_WEIGHTS["ocr_char_similarity"] * (ocr_similarity or 0.0)
        )
        records.append({
            "case_id": case["id"],
            "split": case["split"],
            "source_group": case["source_group"],
            "image": case["image"],
            "prediction_present": prediction is not None,
            "detected_source": source if source_ok else None,
            "translation": translation if translation_ok else None,
            "ocr_cer": ocr_cer,
            "ocr_char_similarity": ocr_similarity,
            "translation_char_score": translation_score,
            "required_terms_recall": terms_recall,
            "quality_score": quality_score,
            "stages_ms": dict(prediction.get("stages_ms", {})) if prediction else {},
        })
    return records

def evaluate_benchmark(
    manifest: Mapping[str, Any] | str | Path,
    predictions: Sequence[Mapping[str, Any]] | str | Path,
) -> dict[str, Any]:
    manifest_data = load_manifest(manifest) if isinstance(manifest, (str, Path)) else dict(manifest)
    cases = validate_manifest(manifest_data)
    payload = _read_json(predictions) if isinstance(predictions, (str, Path)) else predictions
    records = _evaluate_cases(cases, load_prediction_records(_prediction_items(payload)))
    split_order = {"train": 0, "dev": 1, "test": 2}
    splits = sorted({case["split"] for case in cases}, key=split_order.__getitem__)
    return {
        "manifest": manifest_data.get("dataset", str(manifest)),
        "case_count": len(cases),
        "prediction_count": len(records) - sum(not record["prediction_present"] for record in records),
        "accuracy": _accuracy(records),
        "quality_score": _summary(
            (record["quality_score"] for record in records),
            len(records),
        ),
        "quality_weights": dict(QUALITY_WEIGHTS),
        "by_split": {
            split: {
                "accuracy": _accuracy([
                    record for record in records if record["split"] == split
                ]),
                "quality_score": _summary(
                    (
                        record["quality_score"]
                        for record in records
                        if record["split"] == split
                    ),
                    sum(record["split"] == split for record in records),
                ),
            }
            for split in splits
        },
        "latency": _latency(records),
        "cases": records,
    }


def evaluate(manifest: Mapping[str, Any] | str | Path, predictions: Sequence[Mapping[str, Any]] | str | Path) -> dict[str, Any]:
    return evaluate_benchmark(manifest, predictions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate source-disjoint translation predictions")
    parser.add_argument("manifest", help="manifest JSON path")
    parser.add_argument("predictions", help="prediction JSON path")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def _print_summary(result: Mapping[str, Any]) -> None:
    accuracy = result["accuracy"]
    print(
        "Translation E2E Summary: "
        f"cases={result['case_count']} predictions={result['prediction_count']} "
        f"ocr_similarity={accuracy['ocr_char_similarity']['avg']!s} "
        f"translation={accuracy['translation_char_score']['avg']!s} "
f"required_terms={accuracy['required_terms_recall']['avg']!s} "
        f"quality={result['quality_score']['avg']!s}"
    )
    print("Latency:")
    for stage, stats in result["latency"].items():
        avg = "n/a" if stats["avg"] is None else f"{stats['avg']:.1f}"
        p95 = "n/a" if stats["p95"] is None else f"{stats['p95']:.1f}"
        print(f"- {stage}: avg_ms={avg} p95_ms={p95} coverage={stats['coverage']:.1%}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = evaluate_benchmark(args.manifest, args.predictions)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
