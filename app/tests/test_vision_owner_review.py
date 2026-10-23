import hashlib
from pathlib import Path

import pytest

import vision_owner_review as review


def _write_image(root: Path, name: str, payload: bytes) -> tuple[str, str]:
    path = root / "images" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return str(path.relative_to(root)), hashlib.sha256(payload).hexdigest()


def _case(root: Path, case_id: str = "case-a", *, family: str = "family-a", payload: bytes = b"image-a") -> dict:
    image, image_sha256 = _write_image(root, f"{case_id}.png", payload)
    return {
        "id": case_id,
        "image": image,
        "source_family": family,
        "image_sha256": image_sha256,
        "annotation_revision": "r1",
        "source_lang": "ja",
        "target_lang": "zh-Hant",
        "candidate_source": "候補原文",
        "candidate_translations": ["候補翻譯"],
        "required_terms": ["術語"],
        "difficulty_tags": ["blur"],
        "owner_confirmation": "pending",
        "provenance_confirmed_by_owner": False,
        "provenance_note": "來源：遊戲截圖《雲姬》（待確認）",
        "candidate_uncertainties": ["角色名「雲姬」讀法？"],
        "ignore_notes": ["忽略 UI：HP 100%"],
    }


def test_validation_requires_actual_hash_and_workspace_containment(tmp_path):
    case = _case(tmp_path)
    case["image_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        review.validate_review_cases([case], tmp_path)

    escaped = _case(tmp_path, "escape")
    escaped["image"] = "../outside.png"
    with pytest.raises(ValueError, match="workspace root"):
        review.validate_review_cases([escaped], tmp_path)


def test_review_metadata_fields_are_all_required(tmp_path):
    for field in ("provenance_note", "candidate_uncertainties", "ignore_notes"):
        case = _case(tmp_path, case_id=f"missing-{field}")
        case.pop(field)
        with pytest.raises(ValueError, match=f"missing required fields: {field}"):
            review.validate_review_cases([case], tmp_path)


def test_review_metadata_requires_provenance_note_and_string_lists(tmp_path):
    case = _case(tmp_path)
    case["provenance_note"] = " "
    with pytest.raises(ValueError, match="provenance_note"):
        review.validate_review_cases([case], tmp_path)

    for field in ("candidate_uncertainties", "ignore_notes"):
        case = _case(tmp_path, case_id=f"bad-{field}")
        case[field] = [""]
        with pytest.raises(ValueError, match=field):
            review.validate_review_cases([case], tmp_path)


def test_review_metadata_note_lists_may_be_empty(tmp_path):
    case = _case(tmp_path)
    case["candidate_uncertainties"] = []
    case["ignore_notes"] = []
    assert review.validate_review_cases([case], tmp_path)[0]["ignore_notes"] == []

def test_selection_rejects_blocked_family_or_hash(tmp_path):
    case = _case(tmp_path)
    with pytest.raises(ValueError, match="blocked source_family"):
        review.select_review_cases([case], tmp_path, blocked_source_families={case["source_family"]})
    with pytest.raises(ValueError, match="blocked image_sha256"):
        review.select_review_cases([case], tmp_path, blocked_image_sha256s={case["image_sha256"]})


def test_selection_is_deterministic_and_limited_to_one_per_family(tmp_path):
    cases = [
        _case(tmp_path, "z", family="same", payload=b"z"),
        _case(tmp_path, "a", family="same", payload=b"a"),
        _case(tmp_path, "b", family="other", payload=b"b"),
    ]
    expected = sorted(
        cases,
        key=lambda item: hashlib.sha256(
            ("CH-owner-review-v1\0" + item["source_family"] + "\0" + item["image_sha256"]).encode("utf-8")
        ).hexdigest(),
    )
    selected = review.select_review_cases(list(reversed(cases)), tmp_path)
    assert [item["id"] for item in selected] == [
        item["id"] for item in expected if item["source_family"] != "same" or item["id"] == next(
            candidate["id"] for candidate in expected if candidate["source_family"] == "same"
        )
    ]
    assert sum(item["source_family"] == "same" for item in selected) == 1
    assert selected == review.select_review_cases(cases, tmp_path)


@pytest.mark.parametrize("field, value", [
    ("owner_confirmation", "pending"),
    ("provenance_confirmed_by_owner", False),
    ("confirmed_source", ""),
    ("confirmed_translations", []),
])
def test_pending_or_incomplete_review_cannot_promote(tmp_path, field, value):
    case = _case(tmp_path)
    case.update({
        "owner_confirmation": "confirmed",
        "provenance_confirmed_by_owner": True,
        "confirmed_source": "已確認原文",
        "confirmed_translations": ["已確認翻譯"],
    })
    case[field] = value
    with pytest.raises(ValueError, match=field):
        review.promote_review([case], tmp_path)


def test_candidate_text_cannot_auto_promote(tmp_path):
    case = _case(tmp_path)
    case.update({
        "owner_confirmation": "confirmed",
        "provenance_confirmed_by_owner": True,
    })
    with pytest.raises(ValueError, match="confirmed_source"):
        review.promote_review([case], tmp_path)


def test_direct_promotion_revalidates_image_hash(tmp_path):
    case = _case(tmp_path)
    case.update({
        "owner_confirmation": "confirmed",
        "provenance_confirmed_by_owner": True,
        "confirmed_source": "已確認原文",
        "confirmed_translations": ["已確認翻譯"],
        "image_sha256": "0" * 64,
    })
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        review.promote_review([case], tmp_path)


def test_direct_promotion_rejects_blocked_family(tmp_path):
    case = _case(tmp_path)
    case.update({
        "owner_confirmation": "confirmed",
        "provenance_confirmed_by_owner": True,
        "confirmed_source": "已確認原文",
        "confirmed_translations": ["已確認翻譯"],
    })
    with pytest.raises(ValueError, match="blocked source_family"):
        review.promote_review(
            [case],
            tmp_path,
            blocked_source_families={case["source_family"]},
        )

def test_happy_promotion_emits_vision_e2e_manifest_fields(tmp_path):
    case = _case(tmp_path)
    case.update({
        "owner_confirmation": "confirmed",
        "provenance_confirmed_by_owner": True,
        "confirmed_source": "已確認原文",
        "confirmed_translations": ["已確認翻譯"],
    })
    manifest = review.promote_review([case], tmp_path)
    assert manifest["version"] == 1
    promoted = manifest["cases"][0]
    assert promoted["reference_source"] == "已確認原文"
    assert promoted["reference_translations"] == ["已確認翻譯"]
    assert promoted["usage_status"] == "locked_test"
    assert promoted["split"] == "test"
    assert promoted["ground_truth_confirmed_by_owner"] is True
    assert {"provenance_note", "candidate_uncertainties", "ignore_notes"}.isdisjoint(promoted)
    assert {"id", "image", "source_family", "image_sha256", "annotation_revision", "source_lang", "target_lang", "required_terms"} <= set(promoted)


def test_markdown_is_unicode_safe_and_marks_candidates_as_pending(tmp_path):
    case = _case(tmp_path, payload="圖片".encode("utf-8"))
    markdown = review.render_review_markdown([case])
    assert "![case-a](images/case-a.png)" in markdown
    assert "候補原文" in markdown
    assert "候補翻譯" in markdown
    assert "來源：遊戲截圖《雲姬》（待確認）" in markdown
    assert "角色名「雲姬」讀法？" in markdown
    assert "忽略 UI：HP 100%" in markdown
    assert "待 owner 確認" in markdown
    assert "已確認原文" not in markdown

def test_markdown_optional_validation_rejects_blocked_case(tmp_path):
    case = _case(tmp_path)
    with pytest.raises(ValueError, match="blocked source_family"):
        review.render_review_markdown(
            [case],
            workspace_root=tmp_path,
            blocked_source_families={case["source_family"]},
        )

def test_markdown_image_url_is_relative_to_nested_output_path(tmp_path):
    case = _case(tmp_path, case_id="nested")
    payload = "實際圖片".encode("utf-8")
    image_path = tmp_path / "example" / "雲 姬.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(payload)
    case["image"] = str(image_path.relative_to(tmp_path))
    case["image_sha256"] = hashlib.sha256(payload).hexdigest()

    markdown = review.render_review_markdown(
        [case],
        workspace_root=tmp_path,
        markdown_output_path=tmp_path / "records" / "private" / "review.md",
    )

    assert "![nested](<../../example/雲 姬.png>)" in markdown


def test_markdown_output_path_cannot_escape_workspace(tmp_path):
    case = _case(tmp_path)
    with pytest.raises(ValueError, match="markdown_output_path.*workspace root"):
        review.render_review_markdown(
            [case],
            workspace_root=tmp_path,
            markdown_output_path=tmp_path.parent / "escaped-review.md",
        )