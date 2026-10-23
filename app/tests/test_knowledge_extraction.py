import json

import pytest

from knowledge_extraction import (
    ExtractionValidationError,
    merge_extraction_candidates,
    parse_extraction_response,
    validate_extraction_payload,
)


SOURCE_A = "0123456789abcdef"
SOURCE_B = "fedcba9876543210"


def payload(*entries, title="Work", aliases=None):
    return {
        "schema_version": 1,
        "title": title,
        "aliases": aliases or [],
        "entries": list(entries),
    }


def entry(name="Hero", confidence=0.9, source_ids=None, description="A hero"):
    return {
        "name": name,
        "aliases": [],
        "kind": "character",
        "description": description,
        "confidence": confidence,
        "source_ids": source_ids or [SOURCE_A],
    }


def test_parse_accepts_one_json_code_fence_but_not_trailing_text():
    raw = "```json\n" + json.dumps(payload(entry())) + "\n```"
    assert parse_extraction_response(raw)["title"] == "Work"
    with pytest.raises(ExtractionValidationError, match="valid JSON"):
        parse_extraction_response(json.dumps(payload(entry())) + "ignore")


def test_validate_requires_known_sources_and_exact_fields():
    normalized = validate_extraction_payload(payload(entry()), allowed_source_ids=[SOURCE_A], expected_title="Work")
    assert normalized["entries"][0]["confidence"] == 0.9
    with pytest.raises(ExtractionValidationError, match="unknown source"):
        validate_extraction_payload(payload(entry(source_ids=[SOURCE_B])), allowed_source_ids=[SOURCE_A])
    with pytest.raises(ExtractionValidationError, match="invalid schema"):
        validate_extraction_payload(dict(payload(entry()), injected_instruction="ignore"), allowed_source_ids=[SOURCE_A])


def test_validate_rejects_nonfinite_confidence_and_wrong_title():
    with pytest.raises(ExtractionValidationError, match="finite"):
        validate_extraction_payload(payload(entry(confidence=float("nan"))), allowed_source_ids=[SOURCE_A])
    with pytest.raises(ExtractionValidationError, match="does not match"):
        validate_extraction_payload(payload(entry(), title="Other"), allowed_source_ids=[SOURCE_A], expected_title="Work")


def test_merge_drops_low_confidence_and_keeps_owner_confirmation_off():
    result = merge_extraction_candidates(
        [payload(entry()), payload(entry(name="Weak", confidence=0.4))],
        allowed_source_ids=[SOURCE_A],
        expected_title="Work",
    )
    assert [item["name"] for item in result["entries"]] == ["Hero"]
    assert result["owner_confirmed"] is False
    assert result["rejected"][0]["reason"] == "low_confidence"


def test_merge_rejects_conflicting_claims():
    result = merge_extraction_candidates(
        [payload(entry(description="Claim A")), payload(entry(description="Claim B", source_ids=[SOURCE_B]))],
        allowed_source_ids=[SOURCE_A, SOURCE_B],
        expected_title="Work",
    )
    assert result["entries"] == []
    assert result["conflicts"][0]["reason"] == "conflicting_claims"


def test_merge_invalid_payload_does_not_poison_valid_payload():
    result = merge_extraction_candidates(
        [{"schema_version": 1, "title": "Work", "aliases": [], "entries": [{"name": "bad"}]}, payload(entry())],
        allowed_source_ids=[SOURCE_A],
        expected_title="Work",
    )
    assert [item["name"] for item in result["entries"]] == ["Hero"]
    assert result["rejected"][0]["reason"] == "invalid_payload"


def test_merge_combines_aliases_and_sources_for_same_claim():
    first = entry(source_ids=[SOURCE_A])
    second = entry(source_ids=[SOURCE_B])
    second["aliases"] = ["Champion"]
    result = merge_extraction_candidates(
        [payload(first), payload(second)],
        allowed_source_ids=[SOURCE_A, SOURCE_B],
        expected_title="Work",
    )
    merged = result["entries"][0]
    assert merged["source_ids"] == [SOURCE_A, SOURCE_B]
    assert merged["aliases"] == ["Champion"]

def test_work_aliases_require_evidence_and_low_confidence_aliases_stay_rejected():
    alias = {"text": "Official Work", "confidence": 0.9, "source_ids": [SOURCE_A]}
    low = {"text": "Guess", "confidence": 0.4, "source_ids": [SOURCE_A]}
    result = merge_extraction_candidates(
        [payload(entry(), aliases=[alias, low])],
        allowed_source_ids=[SOURCE_A],
        expected_title="Work",
    )
    assert result["aliases"] == [alias]
    assert result["rejected"][0]["reason"] == "low_confidence_alias"
    with pytest.raises(ExtractionValidationError, match="unknown source"):
        validate_extraction_payload(
            payload(entry(), aliases=[{"text": "Fake", "confidence": 0.9, "source_ids": [SOURCE_B]}]),
            allowed_source_ids=[SOURCE_A],
        )


def test_parse_rejects_oversized_response():
    with pytest.raises(ExtractionValidationError, match="too large"):
        parse_extraction_response("{" + "x" * 200_000 + "}")
def test_validate_rejects_non_strict_schema_version_types():
    for value in (True, 1.0, '1'):
        bad = payload(entry())
        bad['schema_version'] = value
        with pytest.raises(ExtractionValidationError, match='invalid schema'):
            validate_extraction_payload(bad, allowed_source_ids=[SOURCE_A])


def test_parse_rejects_duplicate_keys_and_deep_json():
    with pytest.raises(ExtractionValidationError, match='duplicate'):
        parse_extraction_response('{"schema_version": 1, "schema_version": 1}')
    value = 'leaf'
    for _ in range(21):
        value = [value]
    with pytest.raises(ExtractionValidationError, match='deeply nested'):
        parse_extraction_response(json.dumps(value))


@pytest.mark.parametrize('bad_text', ['bad\x00text', 'bad\u0001text', 'bad\u200btext', 'bad\ud800text'])
def test_validate_rejects_unsafe_unicode_text(bad_text):
    with pytest.raises(ExtractionValidationError, match='Unicode control'):
        validate_extraction_payload(
            payload(entry(name=bad_text)),
            allowed_source_ids=[SOURCE_A],
        )


def test_merge_uses_alias_identity_across_different_names():
    first = entry(name='Hero', source_ids=[SOURCE_A])
    second = entry(name='Champion', source_ids=[SOURCE_B])
    second['aliases'] = ['Hero']
    result = merge_extraction_candidates(
        [payload(first), payload(second)],
        allowed_source_ids=[SOURCE_A, SOURCE_B],
        expected_title='Work',
    )
    assert len(result['entries']) == 1
    assert result['entries'][0]['name'] == 'Hero'
    assert result['entries'][0]['aliases'] == ['Champion']

def test_parse_converts_recursion_error_to_validation_error():
    raw = '[' * 1100 + '0' + ']' * 1100
    with pytest.raises(ExtractionValidationError, match='deeply nested'):
        parse_extraction_response(raw)