"""Explicit optional-corpus boundaries for a clean source checkout.

Only five named external-image tests can skip for missing images. Missing or
invalid JSON manifests and unsafe paths remain errors. This checks availability,
not ground truth or image integrity; evaluators retain those responsibilities.
Real quality runs must use pytest --require-external-corpora.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

# Test identities, not globs: adding or renaming a test requires review.
REQUIREMENTS = {
    "tests/test_manga_repeated_run_evaluator.py::test_public_manga_holdout_manifest_is_evaluator_ready":
        ("manifest", "benchmarks/manga_cover_cases.json"),
    "tests/test_manga_repeated_run_evaluator.py::test_owner_confirmed_heavy_knight_manifest_is_locked_and_scored_only_on_explicit_anchors":
        ("manifest", "benchmarks/tensei_heavy_knight_owner_confirmed_ocr.json"),
    "tests/test_temporal_holdout_benchmark.py::test_unicode_safe_loader_reads_owner_confirmed_path":
        ("file", "example/転生重騎士/001.jpg"),
    "tests/test_temporal_holdout_benchmark.py::test_safe_policy_is_lossless_and_near_skip_has_counterexample":
        ("manifest", "benchmarks/temporal_holdout_cases.json"),
    "tests/test_temporal_holdout_benchmark.py::test_cli_emits_locked_frame_policy_metrics":
        ("manifest", "benchmarks/temporal_holdout_cases.json"),
}
MAX_MANIFEST_BYTES = 1024 * 1024


def _inside(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or len(name) > 1024:
        raise ValueError("Corpus path must be bounded, nonempty text")
    normalized = name.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or ".." in relative.parts or ":" in normalized:
        raise ValueError("Corpus path must stay inside the source checkout")
    target = root.joinpath(*relative.parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Corpus symlink escapes the source checkout")
    return target


def missing_files_for_test(root: Path, node_id: str) -> tuple[str, ...]:
    requirement = REQUIREMENTS.get(node_id)
    if requirement is None:
        return ()
    root = Path(root).resolve()
    kind, name = requirement
    target = _inside(root, name)
    if kind == "file":
        if target.exists() and not target.is_file():
            raise ValueError("Corpus image must be a file, not a directory")
        return () if target.is_file() else (name,)
    # Manifests are versioned contracts and must never become optional.
    with target.open("rb") as handle:
        data = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Corpus manifest exceeds the size limit")
    payload = json.loads(data.decode("utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not cases or len(cases) > 4096:
        raise ValueError("Corpus manifest must contain 1..4096 cases")
    missing = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Corpus case must be an object")
        image = case.get("image", case.get("source"))
        if image == "synthetic://local-content-event":
            continue
        path = _inside(root, image)
        if path.exists() and not path.is_file():
            raise ValueError("Corpus image must be a file, not a directory")
        if not path.is_file():
            missing.append(image)
    return tuple(dict.fromkeys(missing))
