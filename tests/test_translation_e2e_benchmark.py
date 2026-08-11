import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from translation_e2e_benchmark import (
    _prediction_items,
    evaluate_benchmark,
    load_manifest,
    percentile,
    validate_manifest,
    translation_character_score,
)


def _manifest(*cases):
    return {"version": 1, "cases": list(cases)}


def _case(case_id, source_group="group", split="test"):
    return {
        "id": case_id,
        "source_group": source_group,
        "image": f"example/{case_id}.png",
        "split": split,
        "source_lang": "en",
        "target_lang": "zh-Hant",
        "reference_source": "source text",
        "reference_translations": ["正確翻譯", "另一個正確翻譯"],
        "required_terms": ["正確"],
    }


_MISSING = object()

def _prediction(case_id, source="source text", translation="正確翻譯", stages=_MISSING):
    return {
        "case_id": case_id,
        "detected_source": source,
        "translation": translation,
        "stages_ms": {} if stages is _MISSING else stages,
    }


def test_manifest_text_fields_are_stripped_after_validation() -> None:
    case = _case("a", source_group=" group ")
    case["image"] = " example/a.png "
    case["split"] = " TEST "

    validated = validate_manifest(_manifest(case))

    assert validated[0]["source_group"] == "group"
    assert validated[0]["split"] == "test"


@pytest.mark.parametrize("blank", ["", " \t\n"])
def test_blank_prediction_text_is_missing_and_scores_zero(blank: str) -> None:
    result = evaluate_benchmark(
        _manifest(_case("a")),
        [_prediction("a", source=blank, translation=blank)],
    )
    record = result["cases"][0]

    assert record["detected_source"] is None
    assert record["translation"] is None
    assert record["ocr_char_similarity"] is None
    assert record["translation_char_score"] is None
    assert record["required_terms_recall"] is None
    assert record["quality_score"] == 0.0


def test_prediction_defaults_only_absent_or_null_stages_to_empty_mapping() -> None:
    absent = _prediction("a")
    absent.pop("stages_ms")
    null = _prediction("a", stages=None)

    for prediction in (absent, null):
        result = evaluate_benchmark(_manifest(_case("a")), [prediction])
        assert result["cases"][0]["stages_ms"] == {}


@pytest.mark.parametrize("stages", [[], "", 0, False])
def test_prediction_rejects_non_mapping_stages(stages) -> None:
    with pytest.raises(ValueError, match="stages_ms must be an object"):
        evaluate_benchmark(_manifest(_case("a")), [_prediction("a", stages=stages)])


def test_manifest_rejects_source_group_crossing_splits() -> None:
    with pytest.raises(ValueError, match="crosses splits"):
        validate_manifest(_manifest(
            _case("a", source_group="same", split="train"),
            _case("b", source_group="same", split="test"),
        ))


def test_manifest_rejects_same_image_crossing_splits_under_different_groups() -> None:
    first = _case("a", source_group="group-a", split="train")
    second = _case("b", source_group="group-b", split="test")
    second["image"] = first["image"]

    with pytest.raises(ValueError, match="image .* crosses splits"):
        validate_manifest(_manifest(first, second))

def test_long_substring_translation_is_not_full_credit() -> None:
    score = translation_character_score(
        "正確翻譯，但這是一段額外的長輸出，包含許多不必要內容。",
        ["正確翻譯"],
    )
    assert 0.0 < score < 1.0


def test_multiple_references_choose_best_character_score() -> None:
    assert translation_character_score("候選翻譯B", ["候選翻譯A", "候選翻譯B"]) == 1.0


def test_accuracy_first_aggregation() -> None:
    result = evaluate_benchmark(
        _manifest(_case("a"), _case("b", source_group="other")),
        [_prediction("a"), _prediction("b", source="", translation="只含正確")],
    )
    assert result["accuracy"]["translation_char_score"]["avg"] < 1.0
    assert result["accuracy"]["required_terms_recall"]["avg"] == 1.0
    assert 0.0 < result["quality_score"]["avg"] < 1.0
    assert result["quality_weights"] == {
        "translation_char_score": 0.65,
        "required_terms_recall": 0.20,
        "ocr_char_similarity": 0.15,
    }
    assert list(result)[:4] == ["manifest", "case_count", "prediction_count", "accuracy"]


def test_missing_prediction_scores_zero_in_quality_aggregate() -> None:
    result = evaluate_benchmark(
        _manifest(_case("a"), _case("b", source_group="other")),
        [_prediction("a")],
    )

    assert result["quality_score"]["avg"] == 0.5
    assert result["quality_score"]["coverage"] == 1.0
    assert result["prediction_count"] == 1

def test_latency_coverage_and_p95_do_not_treat_missing_as_zero() -> None:
    result = evaluate_benchmark(
        _manifest(_case("a"), _case("b", source_group="other")),
        [
            _prediction("a", stages={"capture": 10, "ocr": 20, "total": 100}),
            _prediction("b", stages={"capture": 30}),
        ],
    )
    assert result["latency"]["capture"] == {
        "avg": 20.0, "p95": 30.0, "coverage": 1.0, "count": 2, "total_cases": 2
    }
    assert result["latency"]["ocr"]["avg"] == 20.0
    assert result["latency"]["ocr"]["coverage"] == 0.5
    assert result["latency"]["model"]["avg"] is None
    assert result["latency"]["model"]["p95"] is None
    assert result["latency"]["translation"]["avg"] is None
    assert result["latency"]["translation"]["coverage"] == 0.0
    assert result["latency"]["total"]["avg"] == 100.0
    assert result["latency"]["total"]["coverage"] == 0.5


def test_percentile_uses_nearest_rank_without_interpolation() -> None:
    assert percentile([10, 20, 30, 40]) == 40.0


def test_cli_json_reads_manifest_and_predictions_without_model() -> None:
    script = Path(__file__).resolve().parents[1] / "translation_e2e_benchmark.py"
    manifest = Path(__file__).resolve().parents[1] / "benchmarks" / "translation_e2e_cases.json"
    predictions = [_prediction(
        "quote-cn-to-en",
        source="我到河北省來",
        translation="I came to Hebei Province.",
        stages={"total": 12},
    )]
    completed = subprocess.run(
        [sys.executable, str(script), str(manifest), "-", "--json"],
        input=json.dumps(predictions, ensure_ascii=False),
        check=True, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    output = json.loads(completed.stdout)
    assert output["case_count"] == 6
    assert output["prediction_count"] == 1
    assert output["latency"]["total"]["avg"] == 12.0
    assert output["latency"]["total"]["coverage"] == 1 / 6
    assert "runtime" in output["latency"]

def test_manifest_normalizes_all_text_fields_and_ids() -> None:
    case = _case(" case-a ", source_group=" group ")
    case.update({
        "image": " example/a.png ",
        "source_lang": " en ",
        "target_lang": " zh-Hant ",
        "reference_source": " source text ",
        "reference_translations": [" 正確翻譯 "],
        "required_terms": [" 正確 "],
    })

    validated = validate_manifest(_manifest(case))[0]

    assert validated["id"] == "case-a"
    assert validated["image"] == "example/a.png"
    assert validated["source_lang"] == "en"
    assert validated["target_lang"] == "zh-Hant"
    assert validated["reference_source"] == "source text"
    assert validated["reference_translations"] == ["正確翻譯"]
    assert validated["required_terms"] == ["正確"]


def test_prediction_items_accepts_non_string_sequences() -> None:
    predictions = (_prediction("a"), _prediction("b"))

    assert _prediction_items(predictions) == list(predictions)
    assert _prediction_items({"predictions": predictions}) == list(predictions)


def test_prediction_case_id_is_stripped_before_matching() -> None:
    result = evaluate_benchmark(_manifest(_case("a")), [_prediction(" a ")])

    assert result["prediction_count"] == 1
    assert result["cases"][0]["case_id"] == "a"
