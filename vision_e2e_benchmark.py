"""Model-free paired Vision E2E evaluator with provenance and promotion gates."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

import translation_e2e_benchmark as translation

REPEATS = 5
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROVIDER_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,63}$")
FALLBACK_TOKEN_RE = re.compile(r"^(?:[a-z0-9][a-z0-9_.:-]{0,63})?$")
REPORT_RECORD_FIELDS = (
    "case_id",
    "repeat",
    "condition",
    "condition_fingerprint",
    "provider",
    "fallback_reason",
    "runtime_mode",
    "residual_processes",
    "stages_ms",
    "quality_score",
    "ocr_char_similarity",
    "translation_char_score",
    "required_terms_recall",
    "nonempty",
    "image_sha256",
    "annotation_revision",
)
HASH_FIELDS = ("model_sha256", "runtime_sha256", "prompt_sha256")
FIXED_CONDITION_FIELDS = (
    *HASH_FIELDS,
    "target",
    "sampling",
    "context",
    "gpu_mode",
)
IDENTITY_FIELDS = frozenset({"condition_id", "condition", "name", "route", "route_id"})
ALLOWED_CONDITION_FIELDS = frozenset(FIXED_CONDITION_FIELDS) | IDENTITY_FIELDS
PROVENANCE_FIELDS = (
    "source_family",
    "image_sha256",
    "annotation_revision",
    "usage_status",
    "ground_truth_confirmed_by_owner",
)
ALLOWED_USAGE = frozenset({"development", "locked_test", "public_audit"})
LOCKED_USAGE = frozenset({"locked_test", "public_audit"})
SENSITIVE_FIELDS = frozenset({
    "detected_source",
    "translation",
    "prompt",
    "image_bytes",
    "source_text",
    "ocr_text",
    "raw_text",
    "raw_model_output",
    "image_data",
    "image_parts",
    "authorization",
    "token",
    "access_token",
    "auth_token",
    "id_token",
    "refresh_token",
    "bearer_token",
    "api_token",
    "api_key",
})


def canonical_sha256(value: Any) -> str:
    """Return a deterministic SHA-256 for JSON-compatible benchmark metadata."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _nonempty_text(value: Any, field: str, owner: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner} field {field!r} must be a non-empty string")
    return value.strip()


def validate_manifest(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate translation fields plus immutable visual provenance per split."""
    cases = translation.validate_manifest(manifest)
    family_splits: dict[str, str] = {}
    hash_splits: dict[str, str] = {}
    validated: list[dict[str, Any]] = []

    for raw in cases:
        case_id = raw["id"]
        owner = f"case {case_id!r}"
        missing = [field for field in PROVENANCE_FIELDS if field not in raw]
        if missing:
            raise ValueError(
                f"{owner} missing provenance fields: {', '.join(missing)}"
            )

        family = _nonempty_text(raw["source_family"], "source_family", owner)
        image_sha = _nonempty_text(raw["image_sha256"], "image_sha256", owner)
        annotation = _nonempty_text(
            raw["annotation_revision"], "annotation_revision", owner
        )
        usage = _nonempty_text(raw["usage_status"], "usage_status", owner).lower()
        confirmed = raw["ground_truth_confirmed_by_owner"]

        if not SHA256_RE.fullmatch(image_sha):
            raise ValueError(
                f"{owner} image_sha256 must be 64 lowercase hex characters"
            )
        if usage not in ALLOWED_USAGE:
            raise ValueError(
                f"{owner} usage_status must be one of: "
                f"{', '.join(sorted(ALLOWED_USAGE))}"
            )
        if not isinstance(confirmed, bool):
            raise ValueError(
                f"{owner} ground_truth_confirmed_by_owner must be a boolean"
            )
        if usage in LOCKED_USAGE and confirmed is not True:
            raise ValueError(
                f"{owner} ground_truth_confirmed_by_owner must be true "
                f"for {usage}"
            )

        split = raw["split"]
        allowed_for_split = (
            LOCKED_USAGE if split == "test" else frozenset({"development"})
        )
        if usage not in allowed_for_split:
            raise ValueError(
                f"{owner} split {split!r} is incompatible with "
                f"usage_status {usage!r}"
            )
        if usage in LOCKED_USAGE and any(
            bool(raw.get(key))
            for key in ("tunable", "tunable_state", "tunable_parameters")
        ):
            raise ValueError(
                f"{owner} locked usage_status cannot have tunable state"
            )

        previous = family_splits.setdefault(family, split)
        if previous != split:
            raise ValueError(
                f"source_family {family!r} crosses splits: "
                f"{previous!r} and {split!r}"
            )
        previous = hash_splits.setdefault(image_sha, split)
        if previous != split:
            raise ValueError(
                f"image_sha256 {image_sha!r} crosses splits: "
                f"{previous!r} and {split!r}"
            )

        validated.append({
            **raw,
            "source_family": family,
            "image_sha256": image_sha,
            "annotation_revision": annotation,
            "usage_status": usage,
            "ground_truth_confirmed_by_owner": confirmed,
        })
    return validated


def _condition_route(condition: Mapping[str, Any]) -> str:
    return _nonempty_text(condition.get("route"), "route", "condition")


def condition_fingerprint(condition: Mapping[str, Any]) -> str:
    """Fingerprint fixed controls while deliberately excluding condition identity."""
    if not isinstance(condition, Mapping):
        raise ValueError("condition must be an object")
    missing = [field for field in FIXED_CONDITION_FIELDS if field not in condition]
    if missing:
        raise ValueError(f"condition missing fields: {', '.join(missing)}")
    unsupported = sorted(set(condition) - ALLOWED_CONDITION_FIELDS)
    if unsupported:
        raise ValueError(
            f"condition has unsupported fields: {', '.join(unsupported)}"
        )

    _condition_route(condition)
    clean = {
        key: value
        for key, value in condition.items()
        if key not in IDENTITY_FIELDS
    }
    for field in HASH_FIELDS:
        value = clean[field]
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            raise ValueError(
                f"condition field {field!r} must be 64 lowercase hex characters"
            )
    for field in ("target", "gpu_mode"):
        clean[field] = _nonempty_text(clean[field], field, "condition")
    clean["gpu_mode"] = clean["gpu_mode"].lower()
    if not isinstance(clean["sampling"], Mapping):
        raise ValueError("condition sampling must be an object")
    if not isinstance(clean["context"], Mapping):
        raise ValueError("condition context must be an object")
    return canonical_sha256(clean)


def _clean_stages(value: Any, label: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"record {label!r} stages_ms must be an object")

    result: dict[str, float] = {}
    for stage, raw in value.items():
        if not isinstance(stage, str) or not stage.strip() or isinstance(raw, bool):
            raise ValueError(f"record {label!r} has invalid stage")
        stage = stage.strip()
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"record {label!r} stage {stage!r} must be numeric"
            ) from exc
        if not math.isfinite(number) or number < 0:
            raise ValueError(
                f"record {label!r} stage {stage!r} must be finite and >= 0"
            )
        result[stage] = number
    return result


def _validate_run(
    run: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    label: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if (
        not isinstance(run, Mapping)
        or not isinstance(run.get("condition"), Mapping)
        or not isinstance(run.get("records"), list)
    ):
        raise ValueError(f"{label} run must contain condition and records")

    condition = dict(run["condition"])
    fingerprint = condition_fingerprint(condition)
    known_ids = {case["id"] for case in cases}
    expected = {
        (case_id, repeat)
        for case_id in known_ids
        for repeat in range(1, REPEATS + 1)
    }
    seen: set[tuple[str, int]] = set()
    records: list[dict[str, Any]] = []

    for index, raw in enumerate(run["records"]):
        if not isinstance(raw, Mapping):
            raise ValueError(f"{label} record at index {index} must be an object")
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{label} record at index {index} needs case_id")
        case_id = case_id.strip()
        if case_id not in known_ids:
            raise ValueError(f"{label} records contain unknown case_id {case_id!r}")

        repeat = raw.get("repeat")
        if (
            isinstance(repeat, bool)
            or not isinstance(repeat, int)
            or repeat not in range(1, REPEATS + 1)
        ):
            raise ValueError(f"{label} record {case_id!r} has invalid repeat")
        key = (case_id, repeat)
        if key in seen:
            raise ValueError(
                f"{label} records contain duplicate case/repeat {key!r}"
            )
        seen.add(key)

        if "runtime_mode" not in raw:
            raise ValueError(f"{label} record {case_id!r} missing runtime_mode")
        runtime_mode = _nonempty_text(
            raw["runtime_mode"], "runtime_mode", f"{label} record {case_id!r}"
        ).lower()
        if "residual_processes" not in raw:
            raise ValueError(
                f"{label} record {case_id!r} missing residual_processes"
            )
        residual = raw["residual_processes"]
        if (
            isinstance(residual, bool)
            or not isinstance(residual, int)
            or residual < 0
        ):
            raise ValueError(
                f"{label} record {case_id!r} residual_processes "
                "must be an integer >= 0"
            )

        if "provider" not in raw:
            raise ValueError(f"{label} record {case_id!r} missing provider")
        provider = raw["provider"]
        if not isinstance(provider, str) or not PROVIDER_TOKEN_RE.fullmatch(provider):
            raise ValueError(
                f"{label} record {case_id!r} provider must be a safe token"
            )
        if "fallback_reason" not in raw:
            raise ValueError(f"{label} record {case_id!r} missing fallback_reason")
        fallback_reason = raw["fallback_reason"]
        if (
            not isinstance(fallback_reason, str)
            or not FALLBACK_TOKEN_RE.fullmatch(fallback_reason)
        ):
            raise ValueError(
                f"{label} record {case_id!r} fallback_reason must be a safe token"
            )

        record_fingerprint = raw.get("condition_fingerprint", fingerprint)
        if record_fingerprint != fingerprint:
            raise ValueError(
                f"{label} record {case_id!r} condition fingerprint mismatch"
            )
        records.append({
            **dict(raw),
            "case_id": case_id,
            "repeat": repeat,
            "runtime_mode": runtime_mode,
            "residual_processes": residual,
            "provider": provider,
            "fallback_reason": fallback_reason,
            "stages_ms": _clean_stages(raw.get("stages_ms"), case_id),
            "condition_fingerprint": fingerprint,
        })

    missing = sorted(expected - seen)
    if missing:
        raise ValueError(
            f"{label} records missing required case/repeat observations: {missing!r}"
        )
    return condition, records


def _score_records(
    cases: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_case = {case["id"]: case for case in cases}
    scored: list[dict[str, Any]] = []
    for record in records:
        case = by_case[record["case_id"]]
        source = record.get("detected_source")
        output = record.get("translation")
        source_ok = isinstance(source, str) and bool(source.strip())
        output_ok = isinstance(output, str) and bool(output.strip())
        ocr_score = (
            translation.character_similarity(source, case["reference_source"])
            if source_ok
            else None
        )
        translation_score = (
            translation.translation_character_score(
                output, case["reference_translations"]
            )
            if output_ok
            else None
        )
        terms_score = (
            translation.required_terms_recall(output, case["required_terms"])
            if output_ok
            else None
        )
        quality = (
            translation.QUALITY_WEIGHTS["translation_char_score"]
            * (translation_score or 0.0)
            + translation.QUALITY_WEIGHTS["required_terms_recall"]
            * (terms_score or 0.0)
            + translation.QUALITY_WEIGHTS["ocr_char_similarity"]
            * (ocr_score or 0.0)
        )
        scored.append({
            **record,
            "quality_score": quality,
            "ocr_char_similarity": ocr_score,
            "translation_char_score": translation_score,
            "required_terms_recall": terms_score,
            "nonempty": source_ok and output_ok,
            "image_sha256": case["image_sha256"],
            "annotation_revision": case["annotation_revision"],
        })
    return scored


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(records)
    scores = [float(record["quality_score"]) for record in records]
    return {
        "quality": sum(scores) / count if count else None,
        "nonempty_rate": (
            sum(bool(record["nonempty"]) for record in records) / count
            if count
            else 0.0
        ),
        "coverage": 1.0 if count else 0.0,
        "count": count,
    }


def _latency(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for stage in translation.LATENCY_STAGES:
        values = [
            record["stages_ms"][stage]
            for record in records
            if stage in record["stages_ms"]
        ]
        output[stage] = {
            "avg": sum(values) / len(values) if values else None,
            "p95": translation.percentile(values),
            "coverage": len(values) / len(records) if records else 0.0,
        }
    return output


def redact_report(value: Any) -> Any:
    """Remove exact raw-content and credential keys before report emission."""
    if isinstance(value, Mapping):
        return {
            str(key): redact_report(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_FIELDS
        }
    if isinstance(value, list):
        return [redact_report(item) for item in value]
    return value


def evaluate_paired(
    manifest: Mapping[str, Any],
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate exactly five paired repeats and apply an accuracy-first gate."""
    validated_cases = validate_manifest(manifest)
    cases = [
        case
        for case in validated_cases
        if case["usage_status"] in LOCKED_USAGE
    ]
    if not cases:
        raise ValueError(
            "promotion manifest needs at least one locked_test or public_audit case"
        )
    base_condition, base_raw = _validate_run(baseline, cases, "baseline")
    candidate_condition, candidate_raw = _validate_run(
        candidate, cases, "candidate"
    )
    base_route = _condition_route(base_condition)
    candidate_route = _condition_route(candidate_condition)
    if base_route == candidate_route:
        raise ValueError("baseline and candidate routes must be different")

    base_fp = condition_fingerprint(base_condition)
    candidate_fp = condition_fingerprint(candidate_condition)
    if base_fp != candidate_fp:
        raise ValueError(
            "baseline and candidate condition fingerprints must match"
        )

    base = _score_records(
        cases,
        [{**record, "condition": "baseline"} for record in base_raw],
    )
    variant = _score_records(
        cases,
        [{**record, "condition": "candidate"} for record in candidate_raw],
    )
    base_summary = _summary(base)
    variant_summary = _summary(variant)
    base_by_case = {
        case["id"]: sum(
            item["quality_score"]
            for item in base
            if item["case_id"] == case["id"]
        ) / REPEATS
        for case in cases
    }
    variant_by_case = {
        case["id"]: sum(
            item["quality_score"]
            for item in variant
            if item["case_id"] == case["id"]
        ) / REPEATS
        for case in cases
    }
    case_regressions = sorted(
        case_id
        for case_id in base_by_case
        if variant_by_case[case_id] < base_by_case[case_id] - 1e-12
    )

    reasons: list[str] = []
    if (
        variant_summary["quality"] < base_summary["quality"] - 1e-12
        or case_regressions
    ):
        reasons.append("quality_regression")
    if (
        variant_summary["nonempty_rate"]
        < base_summary["nonempty_rate"] - 1e-12
    ):
        reasons.append("nonempty_regression")
    if variant_summary["coverage"] < base_summary["coverage"] - 1e-12:
        reasons.append("coverage_regression")

    quality_reasons = {
        "quality_regression",
        "nonempty_regression",
        "coverage_regression",
    }
    quality_passed = not any(reason in quality_reasons for reason in reasons)

    base_latency = _latency(base)
    candidate_latency = _latency(variant)
    if (
        base_latency["total"]["coverage"] < 1.0
        or candidate_latency["total"]["coverage"] < 1.0
    ):
        reasons.append("total_latency_coverage_required")
    if any(
        candidate_latency[stage]["coverage"]
        < base_latency[stage]["coverage"] - 1e-12
        for stage in translation.LATENCY_STAGES
    ):
        reasons.append("stage_coverage_regression")

    if (
        base_condition["gpu_mode"].strip().lower() != "gpu"
        or candidate_condition["gpu_mode"].strip().lower() != "gpu"
    ):
        reasons.append("gpu_mode_required")
    if any(record["runtime_mode"] != "gpu" for record in [*base, *variant]):
        reasons.append("gpu_runtime_mode_required")
    if any(record["residual_processes"] != 0 for record in [*base, *variant]):
        reasons.append("residual_processes_detected")

    report = {
        "metadata": {
            "manifest_sha256": canonical_sha256(manifest),
            "baseline_condition_fingerprint": base_fp,
            "candidate_condition_fingerprint": candidate_fp,
            "repeats": REPEATS,
        },
        "baseline": base_summary,
        "candidate": variant_summary,
        "per_case": [
            {
                "case_id": case_id,
                "baseline_quality": base_by_case[case_id],
                "candidate_quality": variant_by_case[case_id],
                "delta": variant_by_case[case_id] - base_by_case[case_id],
            }
            for case_id in sorted(base_by_case)
        ],
        "promotion_gate": {
            "passed": not reasons,
            "quality_passed": quality_passed,
            "case_regressions": case_regressions,
            "reasons": reasons,
        },
        "latency": (
            {"baseline": base_latency, "candidate": candidate_latency}
            if quality_passed
            else None
        ),
        "records": [
            {
                key: record[key]
                for key in REPORT_RECORD_FIELDS
                if key in record
            }
            for record in [*base, *variant]
        ],
    }
    return redact_report(report)
