import json
from pathlib import Path

import pytest

import vision_e2e_benchmark as evaluator


def _case(case_id, *, split="test", family="family-a", image_sha="a" * 64,
          usage=None, owner=True):
    if usage is None:
        usage = "development" if split in {"train", "dev"} else "locked_test"
    return {
        "id": case_id,
        "source_group": f"group-{family}",
        "image": f"images/{case_id}.png",
        "split": split,
        "source_lang": "ja",
        "target_lang": "zh-Hant",
        "reference_source": "原文",
        "reference_translations": ["正確翻譯"],
        "required_terms": ["正確"],
        "source_family": family,
        "image_sha256": image_sha,
        "annotation_revision": "r1",
        "usage_status": usage,
        "ground_truth_confirmed_by_owner": owner,
    }


def _manifest(*cases):
    return {"version": 1, "cases": list(cases)}


def _condition(name, *, gpu_mode="gpu", route="route-a", model_sha="1" * 64, runtime_profile="text"):
    return {
        "condition_id": name,
        "route": route,
        "runtime_profile": runtime_profile,
        "model_sha256": model_sha,
        "runtime_sha256": "2" * 64,
        "prompt_sha256": "3" * 64,
        "target": "zh-Hant",
        "sampling": {"temperature": 0},
        "context": {"window": 4},
        "gpu_mode": gpu_mode,
    }


def _record(case_id, repeat, *, translation="正確翻譯", source="原文", total=20,
            residual=0, runtime_mode="gpu", runtime_profile="text", stages=None,
            source_available=None):
    return {
        "case_id": case_id,
        "repeat": repeat,
        "detected_source": source,
        "translation": translation,
        "provider": "local",
        "fallback_reason": "",
        "stages_ms": {"total": total} if stages is None else dict(stages),
        "runtime_mode": runtime_mode,
        "runtime_profile": runtime_profile,
        "residual_processes": residual,
        **({"source_available": source_available} if source_available is not None else {}),
    }


def _run(condition, cases, **kwargs):
    return {
        "condition": condition,
        "records": [
            _record(
                case["id"], repeat,
                runtime_profile=condition["runtime_profile"],
                **kwargs,
            )
            for case in cases
            for repeat in range(1, 6)
        ],
    }


def test_happy_path_is_paired_redacted_and_quality_first():
    cases = [_case("a"), _case("b", family="family-b", image_sha="b" * 64)]
    report = evaluator.evaluate_paired(
        _manifest(*cases),
        _run(_condition("base"), cases),
        _run(_condition("candidate", route="route-b"), cases, total=10),
    )
    assert report["promotion_gate"]["passed"] is True
    assert report["latency"] is not None
    assert report["latency"]["candidate"]["total"]["coverage"] == 1.0
    assert report["metadata"]["manifest_sha256"] == evaluator.canonical_sha256(_manifest(*cases))
    assert len(report["records"]) == 20
    assert {record["condition"] for record in report["records"]} == {"baseline", "candidate"}
    assert "translation" not in report["records"][0]
    assert "detected_source" not in report["records"][0]


def test_vision_only_quality_uses_translation_basis_without_ocr_source():
    cases = [_case("a")]
    report = evaluator.evaluate_paired(
        _manifest(*cases),
        _run(_condition("base"), cases),
        _run(
            _condition("candidate", route="route-b", runtime_profile="vision"),
            cases,
            source="",
            source_available=False,
        ),
    )

    candidate_records = [
        record for record in report["records"] if record["condition"] == "candidate"
    ]
    assert report["promotion_gate"]["passed"] is True
    assert all(record["quality_basis"] == "translation_only" for record in candidate_records)
    assert all(record["source_available"] is False for record in candidate_records)
    assert all(record["nonempty"] is True for record in candidate_records)
    assert all(record["ocr_char_similarity"] is None for record in candidate_records)


def test_manifest_rejects_source_family_and_image_hash_split_leakage():
    first, second = _case("a", split="train"), _case("b", split="test")
    second["source_group"] = "other-group"
    with pytest.raises(ValueError, match="source_family.*crosses splits"):
        evaluator.validate_manifest(_manifest(first, second))

    first = _case("a", split="train")
    second = _case("b", split="test", family="other", image_sha=first["image_sha256"])
    second["source_group"] = "other-group"
    with pytest.raises(ValueError, match="image_sha256.*crosses splits"):
        evaluator.validate_manifest(_manifest(first, second))


@pytest.mark.parametrize("field,value", [
    ("image_sha256", "A" * 64),
    ("annotation_revision", " "),
])
def test_manifest_rejects_bad_provenance(field, value):
    case = _case("a")
    case[field] = value
    with pytest.raises(ValueError):
        evaluator.validate_manifest(_manifest(case))


@pytest.mark.parametrize("usage", ["unknown", "retired", "LOCKED"])
def test_manifest_rejects_unknown_usage_status(usage):
    with pytest.raises(ValueError, match="usage_status"):
        evaluator.validate_manifest(_manifest(_case("a", usage=usage)))


@pytest.mark.parametrize("case", [
    _case("train-locked", split="train", usage="locked_test"),
    _case("dev-public", split="dev", usage="public_audit"),
    _case("test-development", split="test", usage="development"),
])
def test_manifest_rejects_split_usage_mismatch(case):
    with pytest.raises(ValueError, match="split.*usage_status"):
        evaluator.validate_manifest(_manifest(case))


@pytest.mark.parametrize("usage", ["locked_test", "public_audit"])
def test_locked_or_public_cases_require_owner_confirmation(usage):
    with pytest.raises(ValueError, match="ground_truth_confirmed_by_owner"):
        evaluator.validate_manifest(_manifest(_case("a", usage=usage, owner=False)))


def test_locked_cases_reject_tunable_state():
    case = _case("a")
    case["tunable"] = True
    with pytest.raises(ValueError, match="tunable"):
        evaluator.validate_manifest(_manifest(case))


@pytest.mark.parametrize("field", ["model_sha256", "runtime_sha256", "prompt_sha256"])
@pytest.mark.parametrize("bad_hash", ["a" * 63, "A" * 64, "not-a-hash"])
def test_condition_rejects_bad_locked_hashes(field, bad_hash):
    condition = _condition("base")
    condition[field] = bad_hash
    with pytest.raises(ValueError, match=field):
        evaluator.condition_fingerprint(condition)


def test_condition_rejects_legacy_plaintext_or_unknown_fields():
    condition = _condition("base")
    condition["model"] = "mutable-model-name"
    with pytest.raises(ValueError, match="unsupported fields.*model"):
        evaluator.condition_fingerprint(condition)


def test_routes_must_be_nonempty_and_different():
    cases = [_case("a")]
    with pytest.raises(ValueError, match="route.*non-empty"):
        evaluator.evaluate_paired(
            _manifest(*cases),
            _run(_condition("base", route=" "), cases),
            _run(_condition("candidate", route="b"), cases),
        )
    with pytest.raises(ValueError, match="routes must be different"):
        evaluator.evaluate_paired(
            _manifest(*cases),
            _run(_condition("base", route="same"), cases),
            _run(_condition("candidate", route="same"), cases),
        )


@pytest.mark.parametrize("mutate,pattern", [
    (lambda records: records.pop(), "missing"),
    (lambda records: records.append(dict(records[0])), "duplicate"),
    (lambda records: records.__setitem__(0, {**records[0], "case_id": "unknown"}), "unknown"),
])
def test_records_require_exact_symmetric_five_repeats(mutate, pattern):
    cases = [_case("a")]
    base = _run(_condition("base"), cases)
    candidate = _run(_condition("candidate", route="route-b"), cases)
    mutate(candidate["records"])
    with pytest.raises(ValueError, match=pattern):
        evaluator.evaluate_paired(_manifest(*cases), base, candidate)


def test_condition_mismatch_is_rejected_except_route_identity():
    cases = [_case("a")]
    with pytest.raises(ValueError, match="fingerprints"):
        evaluator.evaluate_paired(
            _manifest(*cases),
            _run(_condition("base"), cases),
            _run(_condition("candidate", route="b", model_sha="4" * 64), cases),
        )


def test_quality_regression_and_speed_cannot_promote():
    cases = [_case("a")]
    report = evaluator.evaluate_paired(
        _manifest(*cases),
        _run(_condition("base"), cases),
        _run(_condition("candidate", route="fast"), cases, translation="錯誤", total=1),
    )
    assert report["promotion_gate"]["passed"] is False
    assert "quality_regression" in report["promotion_gate"]["reasons"]
    assert report["latency"] is None


@pytest.mark.parametrize("missing", ["runtime_mode", "residual_processes"])
def test_records_require_explicit_runtime_evidence(missing):
    cases = [_case("a")]
    candidate = _run(_condition("candidate", route="b"), cases)
    candidate["records"][0].pop(missing)
    with pytest.raises(ValueError, match=missing):
        evaluator.evaluate_paired(
            _manifest(*cases), _run(_condition("base"), cases), candidate
        )


def test_gpu_promotion_checks_every_record_not_only_condition_claim():
    cases = [_case("a")]
    candidate = _run(_condition("candidate", route="b"), cases)
    candidate["records"][0]["runtime_mode"] = "cpu"
    candidate["records"][1]["residual_processes"] = 1
    report = evaluator.evaluate_paired(
        _manifest(*cases), _run(_condition("base"), cases), candidate
    )
    assert report["promotion_gate"]["passed"] is False
    assert set(report["promotion_gate"]["reasons"]) >= {
        "gpu_runtime_mode_required", "residual_processes_detected"
    }


def test_clean_stages_wraps_conversion_errors_as_value_error():
    cases = [_case("a")]
    candidate = _run(_condition("candidate", route="b"), cases)
    candidate["records"][0]["stages_ms"]["total"] = object()
    with pytest.raises(ValueError, match="stage 'total'.*numeric"):
        evaluator.evaluate_paired(
            _manifest(*cases), _run(_condition("base"), cases), candidate
        )


def test_total_stage_requires_full_coverage_and_candidate_cannot_drop_stage_coverage():
    cases = [_case("a")]
    base = _run(_condition("base"), cases, stages={"ocr": 10, "total": 20})
    candidate = _run(_condition("candidate", route="b"), cases, stages={"ocr": 9, "total": 19})
    candidate["records"][0]["stages_ms"].pop("total")
    candidate["records"][1]["stages_ms"].pop("ocr")
    report = evaluator.evaluate_paired(_manifest(*cases), base, candidate)
    assert report["promotion_gate"]["passed"] is False
    assert set(report["promotion_gate"]["reasons"]) >= {
        "total_latency_coverage_required", "stage_coverage_regression"
    }
    assert report["latency"] is not None


def test_fingerprint_is_deterministic_and_ignores_only_condition_identity():
    left = _condition("base", route="a")
    right = _condition("candidate", route="b")
    assert evaluator.condition_fingerprint(left) == evaluator.condition_fingerprint(right)
    assert len(evaluator.condition_fingerprint(left)) == 64


def test_redaction_removes_exact_sensitive_keys_without_overmatching_metrics_or_hashes():
    report = {
        "source_text": "source",
        "ocr_text": "ocr",
        "raw_text": "raw",
        "raw_model_output": "model output",
        "image_data": "bytes",
        "image_parts": ["bytes"],
        "authorization": "Bearer secret",
        "token": "secret",
        "access_token": "secret",
        "api_key": "secret",
        "nested": {"detected_source": "原文", "translation": "秘密"},
        "stages_ms": {"translation": 12.5},
        "latency": {"candidate": {"translation": {"avg": 12.5, "p95": 15.0, "coverage": 1.0}}},
        "translation_char_score": 0.9,
        "prompt_sha256": "3" * 64,
        "case_id": "a",
    }
    assert evaluator.redact_report(report) == {
        "nested": {},
        "stages_ms": {"translation": 12.5},
        "latency": {"candidate": {"translation": {"avg": 12.5, "p95": 15.0, "coverage": 1.0}}},
        "translation_char_score": 0.9,
        "prompt_sha256": "3" * 64,
        "case_id": "a",
    }


def test_runtime_metrics_are_numeric_and_preserved_without_raw_content():
    cases = [_case("a")]
    baseline = _run(_condition("base"), cases)
    candidate = _run(_condition("candidate", route="route-b"), cases)
    for run in (baseline, candidate):
        for record in run["records"]:
            record["runtime_metrics"] = {
                "prompt_tokens": 120,
                "predicted_n": 96,
                "prompt_ms": 12.5,
            }

    report = evaluator.evaluate_paired(_manifest(*cases), baseline, candidate)

    assert report["records"][0]["runtime_metrics"] == {
        "prompt_tokens": 120,
        "predicted_n": 96,
        "prompt_ms": 12.5,
    }


def test_runtime_metrics_reject_raw_or_unsupported_values():
    cases = [_case("a")]
    baseline = _run(_condition("base"), cases)
    candidate = _run(_condition("candidate", route="route-b"), cases)
    candidate["records"][0]["runtime_metrics"] = {"raw_text": "秘密"}

    with pytest.raises(ValueError, match="unsupported runtime metric"):
        evaluator.evaluate_paired(_manifest(*cases), baseline, candidate)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "local\nprivate output"),
        ("fallback_reason", "raw OCR: 秘密"),
    ],
)
def test_report_tokens_reject_unbounded_or_private_text(field, value):
    cases = [_case("a")]
    candidate = _run(_condition("candidate", route="b"), cases)
    candidate["records"][0][field] = value

    with pytest.raises(ValueError, match=field):
        evaluator.evaluate_paired(
            _manifest(*cases), _run(_condition("base"), cases), candidate
        )


def test_report_records_use_allowlist_instead_of_copying_unknown_fields():
    cases = [_case("a")]
    candidate = _run(_condition("candidate", route="b"), cases)
    candidate["records"][0]["secret_payload"] = "must not escape"

    report = evaluator.evaluate_paired(
        _manifest(*cases), _run(_condition("base"), cases), candidate
    )

    assert all("secret_payload" not in record for record in report["records"])

def test_promotion_uses_only_locked_cases_and_rejects_development_records():
    dev = _case("dev", split="dev", family="dev-family", image_sha="d" * 64)
    locked = _case("locked", family="locked-family", image_sha="e" * 64)
    manifest = _manifest(dev, locked)
    baseline = _run(_condition("base"), [locked])
    candidate = _run(_condition("candidate", route="b"), [locked])

    report = evaluator.evaluate_paired(manifest, baseline, candidate)

    assert report["promotion_gate"]["passed"] is True
    assert [case["case_id"] for case in report["per_case"]] == ["locked"]

    baseline["records"].extend(_run(_condition("unused"), [dev])["records"])
    with pytest.raises(ValueError, match="unknown case_id 'dev'"):
        evaluator.evaluate_paired(manifest, baseline, candidate)


def test_promotion_requires_at_least_one_locked_case():
    dev = _case("dev", split="dev", usage="development", owner=False)

    with pytest.raises(ValueError, match="locked_test or public_audit"):
        evaluator.evaluate_paired(
            _manifest(dev),
            _run(_condition("base"), [dev]),
            _run(_condition("candidate", route="b"), [dev]),
        )

def test_ci_inventory_includes_targeted_test():
    inventory = json.loads(
        (Path(__file__).parents[1] / "ci" / "test_groups.json").read_text(encoding="utf-8")
    )
    benchmark_group = next(group for group in inventory["groups"] if group["name"] == "benchmarks")
    assert "tests/test_vision_e2e_benchmark.py" in benchmark_group["test_files"]


def test_route_profiles_may_differ_without_changing_fixed_condition_fingerprint():
    text = _condition("base", route="ocr-first", runtime_profile="text")
    vision = _condition("candidate", route="vision-first", runtime_profile="vision")

    assert evaluator.condition_fingerprint(text) == evaluator.condition_fingerprint(vision)


def test_observed_runtime_profile_must_match_declared_route_profile():
    cases = [_case("a")]
    baseline = _run(_condition("base", route="a", runtime_profile="text"), cases)
    candidate = _run(
        _condition("candidate", route="b", runtime_profile="vision"), cases
    )
    candidate["records"][0]["runtime_profile"] = "text"

    with pytest.raises(ValueError, match="runtime_profile mismatch"):
        evaluator.evaluate_paired(_manifest(*cases), baseline, candidate)


def test_runtime_profile_is_required_and_bounded():
    condition = _condition("base")
    condition.pop("runtime_profile")
    with pytest.raises(ValueError, match="runtime_profile"):
        evaluator.condition_fingerprint(condition)

    condition = _condition("base", runtime_profile="audio")
    with pytest.raises(ValueError, match="runtime_profile"):
        evaluator.condition_fingerprint(condition)
