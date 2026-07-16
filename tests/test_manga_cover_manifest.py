import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "benchmarks" / "manga_cover_cases.json"


def test_manga_cover_manifest_is_holdout_only_and_reproducible() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = manifest["cases"]

    assert manifest["usage_policy"]["holdout_only"] is True
    assert manifest["usage_policy"]["allow_threshold_training"] is False
    assert len(cases) >= 4
    assert len({case["id"] for case in cases}) == len(cases)
    assert len({case["image"] for case in cases}) == len(cases)

    for case in cases:
        assert case["source_page"].startswith("https://commons.wikimedia.org/")
        assert case["download_url"].startswith("https://upload.wikimedia.org/")
        assert case["license"]
        assert case["difficulty_tags"]
        assert case["visible_text_anchors"]
        assert case["year"] <= 1943
        assert case["width"] > 0
        assert case["height"] > 0

        assert isinstance(case["sha256"], str) and case["sha256"]
        assert isinstance(case["bytes"], int) and not isinstance(case["bytes"], bool)
        assert case["bytes"] > 0

        image_path = PROJECT_ROOT / case["image"]
        if image_path.exists():
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            assert digest == case["sha256"]
            assert image_path.stat().st_size == case["bytes"]
