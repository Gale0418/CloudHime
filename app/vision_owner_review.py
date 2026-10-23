"""Owner-confirmed review gates for Vision E2E benchmark cases."""
from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

REVIEW_FIELDS = (
    "id",
    "image",
    "source_family",
    "image_sha256",
    "annotation_revision",
    "source_lang",
    "target_lang",
    "candidate_source",
    "candidate_translations",
    "required_terms",
    "difficulty_tags",
    "provenance_note",
    "candidate_uncertainties",
    "ignore_notes",
    "owner_confirmation",
    "provenance_confirmed_by_owner",
)
SHA256_HEX_LENGTH = 64


def _text(value: Any, field: str, case_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"case {case_id!r} field {field!r} must be a non-empty string")
    return value.strip()


def _text_list(value: Any, field: str, case_id: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"case {case_id!r} field {field!r} must be a string list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"case {case_id!r} field {field!r} must be a string list")
    return [item.strip() for item in value]


def _is_sha256(value: str) -> bool:
    return len(value) == SHA256_HEX_LENGTH and all(char in "0123456789abcdef" for char in value)


def _resolve_image(image: str, workspace_root: Path) -> Path:
    candidate = Path(image)
    path = candidate.resolve() if candidate.is_absolute() else (workspace_root / candidate).resolve()
    try:
        path.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("image path must stay inside workspace root") from exc
    if not path.is_file():
        raise ValueError(f"image does not exist: {image}")
    return path


def _clean_case(raw: Mapping[str, Any], *, workspace_root: Path | None) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("review case must be an object")
    case_id = _text(raw.get("id"), "id", "<unknown>")
    missing = [field for field in REVIEW_FIELDS if field not in raw]
    if missing:
        raise ValueError(f"case {case_id!r} missing required fields: {', '.join(missing)}")

    cleaned = dict(raw)
    for field in ("image", "source_family", "image_sha256", "annotation_revision", "source_lang", "target_lang", "candidate_source", "provenance_note"):
        cleaned[field] = _text(raw[field], field, case_id)
    if not _is_sha256(cleaned["image_sha256"]):
        raise ValueError(f"case {case_id!r} image_sha256 must be 64 lowercase hex characters")
    cleaned["id"] = case_id
    cleaned["candidate_translations"] = _text_list(raw["candidate_translations"], "candidate_translations", case_id, allow_empty=False)
    cleaned["required_terms"] = _text_list(raw["required_terms"], "required_terms", case_id, allow_empty=True)
    cleaned["difficulty_tags"] = _text_list(raw["difficulty_tags"], "difficulty_tags", case_id, allow_empty=True)
    cleaned["candidate_uncertainties"] = _text_list(raw["candidate_uncertainties"], "candidate_uncertainties", case_id, allow_empty=True)
    cleaned["ignore_notes"] = _text_list(raw["ignore_notes"], "ignore_notes", case_id, allow_empty=True)
    confirmation = _text(raw["owner_confirmation"], "owner_confirmation", case_id).lower()
    if confirmation not in {"pending", "confirmed"}:
        raise ValueError(f"case {case_id!r} owner_confirmation must be pending or confirmed")
    cleaned["owner_confirmation"] = confirmation
    if not isinstance(raw["provenance_confirmed_by_owner"], bool):
        raise ValueError(f"case {case_id!r} provenance_confirmed_by_owner must be a boolean")
    cleaned["provenance_confirmed_by_owner"] = raw["provenance_confirmed_by_owner"]

    if workspace_root is not None:
        actual_sha256 = hashlib.sha256(_resolve_image(cleaned["image"], workspace_root).read_bytes()).hexdigest()
        if actual_sha256 != cleaned["image_sha256"]:
            raise ValueError(f"case {case_id!r} image SHA256 mismatch")
    return cleaned


def validate_review_cases(
    cases: Iterable[Mapping[str, Any]],
    workspace_root: str | Path,
    *,
    blocked_source_families: Iterable[str] = (),
    blocked_image_sha256s: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Validate candidate review cases against actual workspace image evidence."""
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise ValueError("workspace root must be an existing directory")
    families = set(blocked_source_families)
    hashes = set(blocked_image_sha256s)
    validated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in cases:
        case = _clean_case(raw, workspace_root=root)
        if case["id"] in seen_ids:
            raise ValueError(f"duplicate case id: {case['id']}")
        seen_ids.add(case["id"])
        if case["source_family"] in families:
            raise ValueError(f"case {case['id']!r} has blocked source_family")
        if case["image_sha256"] in hashes:
            raise ValueError(f"case {case['id']!r} has blocked image_sha256")
        validated.append(case)
    return validated


def _selection_key(case: Mapping[str, Any]) -> str:
    material = f"CH-owner-review-v1\0{case['source_family']}\0{case['image_sha256']}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def select_review_cases(
    cases: Iterable[Mapping[str, Any]],
    workspace_root: str | Path,
    *,
    blocked_source_families: Iterable[str] = (),
    blocked_image_sha256s: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Deterministically select at most one validated image from each family."""
    ordered = sorted(
        validate_review_cases(
            cases,
            workspace_root,
            blocked_source_families=blocked_source_families,
            blocked_image_sha256s=blocked_image_sha256s,
        ),
        key=_selection_key,
    )
    selected: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for case in ordered:
        if case["source_family"] not in seen_families:
            selected.append(case)
            seen_families.add(case["source_family"])
    return selected


def promote_review(
    cases: Iterable[Mapping[str, Any]],
    workspace_root: str | Path,
    *,
    blocked_source_families: Iterable[str] = (),
    blocked_image_sha256s: Iterable[str] = (),
) -> dict[str, Any]:
    """Create a locked manifest only from owner-confirmed, revalidated cases."""
    validated = validate_review_cases(
        cases,
        workspace_root,
        blocked_source_families=blocked_source_families,
        blocked_image_sha256s=blocked_image_sha256s,
    )
    promoted: list[dict[str, Any]] = []
    for case in validated:
        case_id = case["id"]
        if case["owner_confirmation"] != "confirmed":
            raise ValueError(f"case {case_id!r} owner_confirmation must be confirmed")
        if case["provenance_confirmed_by_owner"] is not True:
            raise ValueError(f"case {case_id!r} provenance_confirmed_by_owner must be true")
        confirmed_source = _text(case.get("confirmed_source"), "confirmed_source", case_id)
        confirmed_translations = _text_list(
            case.get("confirmed_translations"),
            "confirmed_translations",
            case_id,
            allow_empty=False,
        )
        promoted.append({
            "id": case_id,
            "source_group": case["source_family"],
            "image": case["image"],
            "split": "test",
            "source_lang": case["source_lang"],
            "target_lang": case["target_lang"],
            "reference_source": confirmed_source,
            "reference_translations": confirmed_translations,
            "required_terms": case["required_terms"],
            "source_family": case["source_family"],
            "image_sha256": case["image_sha256"],
            "annotation_revision": case["annotation_revision"],
            "usage_status": "locked_test",
            "ground_truth_confirmed_by_owner": True,
        })
    if not promoted:
        raise ValueError("at least one confirmed review case is required")
    return {"version": 1, "cases": promoted}


def render_review_markdown(
    cases: Iterable[Mapping[str, Any]],
    workspace_root: str | Path | None = None,
    markdown_output_path: str | Path | None = None,
    *,
    blocked_source_families: Iterable[str] = (),
    blocked_image_sha256s: Iterable[str] = (),
) -> str:
    """Render candidate evidence, optionally with full workspace validation."""
    blocked_families = tuple(blocked_source_families)
    blocked_hashes = tuple(blocked_image_sha256s)
    root: Path | None = None
    output_parent: Path | None = None
    if workspace_root is None:
        if blocked_families or blocked_hashes:
            raise ValueError("workspace_root is required when blocked sets are provided")
        if markdown_output_path is not None:
            raise ValueError("workspace_root is required with markdown_output_path")
        validated = [_clean_case(raw, workspace_root=None) for raw in cases]
    else:
        root = Path(workspace_root).resolve()
        validated = validate_review_cases(
            cases,
            root,
            blocked_source_families=blocked_families,
            blocked_image_sha256s=blocked_hashes,
        )
        if markdown_output_path is not None:
            raw_output = Path(markdown_output_path)
            output_path = (
                raw_output.resolve()
                if raw_output.is_absolute()
                else (root / raw_output).resolve()
            )
            try:
                output_path.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    "markdown_output_path must stay inside workspace root"
                ) from exc
            if output_path == root or output_path.is_dir():
                raise ValueError("markdown_output_path must identify a file inside workspace root")
            output_parent = output_path.parent

    sections = ["# Owner Review（候選資料，非 Ground Truth）"]
    for case in validated:
        uncertainties = case["candidate_uncertainties"] or ["（無）"]
        ignore_notes = case["ignore_notes"] or ["（無）"]
        image_url = case["image"].replace(chr(92), "/")
        if output_parent is not None and root is not None:
            image_path = _resolve_image(case["image"], root)
            image_url = Path(os.path.relpath(image_path, output_parent)).as_posix()
            if any(character.isspace() for character in image_url):
                image_url = f"<{image_url}>"
        sections.extend([
            f"## {case['id']}",
            f"![{case['id']}]({image_url})",
            f"- 來源 family：`{case['source_family']}`（provenance 待 owner 確認）",
            f"- 圖片 SHA256：`{case['image_sha256']}`",
            "- 來源說明（待 owner 確認）：",
            "```text",
            case["provenance_note"],
            "```",
            "- 候選原文（待 owner 確認）：",
            "```text",
            case["candidate_source"],
            "```",
            "- 候選翻譯（待 owner 確認）：",
            *[f"  - {translation}" for translation in case["candidate_translations"]],
            "- 候選疑點（待 owner 確認）：",
            *[f"  - {uncertainty}" for uncertainty in uncertainties],
            "- 建議忽略項（待 owner 確認）：",
            *[f"  - {note}" for note in ignore_notes],
            f"- Owner 狀態：{case['owner_confirmation']}；provenance 待 owner 確認",
        ])
    return "\n".join(sections) + "\n"
