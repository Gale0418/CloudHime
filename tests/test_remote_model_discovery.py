from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
import remote_model_discovery

from model_catalog import MODEL_CATALOG
from remote_model_discovery import (
    DISCOVERY_STATUS_INVALID_KEY,
    DISCOVERY_STATUS_NO_KEY,
    DISCOVERY_STATUS_OFFLINE_SNAPSHOT,
    DISCOVERY_STATUS_UNVERIFIED,
    ModelAvailabilitySnapshot,
    RemoteModelDiscoveryError,
    discover_remote_models,
    fetch_remote_model_records,
    filter_catalog_for_availability,
    load_availability_snapshot,
    normalize_model_id,
    parse_models_page,
    save_availability_snapshot,
)



@pytest.fixture
def local_temp_dir():
    directory = Path.cwd() / ".tmp-remote-model-discovery" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    return directory

class _Response:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


def test_normalize_model_id_accepts_resource_name_and_bare_id():
    assert normalize_model_id("models/gemini-3.6-flash") == "gemini-3.6-flash"
    assert normalize_model_id(" gemma-4-31b-it ") == "gemma-4-31b-it"
    assert normalize_model_id("models/") == ""


def test_parse_models_page_filters_to_generate_content_and_uses_static_image_policy():
    records, next_token = parse_models_page(
        {
            "models": [
                {
                    "name": "models/gemma-3-1b-it",
                    "displayName": "Gemma 3 1B",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-005",
                    "supportedGenerationMethods": ["embedContent"],
                },
                {
                    "name": "models/gemini-4-unknown",
                    "supportedGenerationMethods": ["generateContent"],
                },
            ],
            "nextPageToken": "page-2",
        },
        model_catalog=MODEL_CATALOG,
    )

    assert next_token == "page-2"
    assert [record.model_id for record in records] == [
        "gemma-3-1b-it",
        "gemini-4-unknown",
    ]
    assert records[0].supports_image_input is False
    assert records[1].supports_image_input is False


def test_fetch_remote_model_records_follows_pages_without_leaking_key():
    requests = []
    pages = iter(
        [
            _Response(
                {
                    "models": [
                        {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]}
                    ],
                    "nextPageToken": "next",
                }
            ),
            _Response(
                {
                    "models": [
                        {"name": "models/gemma-4-31b-it", "supportedGenerationMethods": ["generateContent"]}
                    ]
                }
            ),
        ]
    )

    def opener(req, timeout):
        requests.append((req.full_url, dict(req.header_items()), timeout))
        return next(pages)

    records = fetch_remote_model_records("secret-key", urlopen=opener, timeout_seconds=7)

    assert [record.model_id for record in records] == ["gemini-3.6-flash", "gemma-4-31b-it"]
    assert len(requests) == 2
    assert all("secret-key" not in url for url, _, _ in requests)
    assert all(headers.get("X-goog-api-key") == "secret-key" for _, headers, _ in requests)
    assert requests[1][0].endswith("pageSize=1000&pageToken=next")
    assert all(timeout == 7 for _, _, timeout in requests)


def test_fetch_remote_model_records_rejects_repeated_page_token():
    def opener(req, timeout):
        return _Response({"models": [], "nextPageToken": "same"})

    with pytest.raises(RemoteModelDiscoveryError, match="pagination_loop"):
        fetch_remote_model_records("secret-key", urlopen=opener)


def test_no_key_does_not_make_http_request(local_temp_dir):
    called = []

    def opener(*args, **kwargs):
        called.append(True)
        raise AssertionError("network must not be used without a key")

    result = discover_remote_models("  ", snapshot_path=local_temp_dir / "snapshot.json", urlopen=opener)

    assert result.status == DISCOVERY_STATUS_NO_KEY
    assert result.verified is False
    assert called == []
    assert result.available_model_ids == ()


def test_invalid_key_does_not_write_or_reuse_snapshot(local_temp_dir):
    snapshot_path = local_temp_dir / "snapshot.json"

    def opener(req, timeout):
        raise HTTPError(req.full_url, 403, "invalid key", {}, io.BytesIO(b"{}"))

    result = discover_remote_models("bad-key", snapshot_path=snapshot_path, urlopen=opener)

    assert result.status == DISCOVERY_STATUS_INVALID_KEY
    assert result.verified is False
    assert result.available_model_ids == ()
    assert not snapshot_path.exists()


def test_timeout_uses_same_key_last_valid_snapshot(local_temp_dir):
    snapshot_path = local_temp_dir / "snapshot.json"

    def good_opener(req, timeout):
        return _Response(
            {
                "models": [
                    {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]}
                ]
            }
        )

    first = discover_remote_models("same-key", snapshot_path=snapshot_path, urlopen=good_opener)
    assert first.status == "verified"

    def offline_opener(req, timeout):
        raise URLError("offline")

    second = discover_remote_models("same-key", snapshot_path=snapshot_path, urlopen=offline_opener)

    assert second.status == DISCOVERY_STATUS_OFFLINE_SNAPSHOT
    assert second.used_snapshot is True
    assert second.available_model_ids == ("gemini-3.6-flash",)


def test_snapshot_write_failure_keeps_fresh_verified_result(monkeypatch, local_temp_dir):
    def good_opener(req, timeout):
        return _Response(
            {
                "models": [
                    {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]}
                ]
            }
        )

    def fail_write(path, snapshot):
        raise OSError("snapshot destination unavailable")

    monkeypatch.setattr(remote_model_discovery, "save_availability_snapshot", fail_write)
    result = discover_remote_models(
        "same-key",
        snapshot_path=local_temp_dir / "snapshot.json",
        urlopen=good_opener,
    )

    assert result.status == "verified"
    assert result.verified is True
    assert result.error_code == "snapshot_write_failed"
    assert result.available_model_ids == ("gemini-3.6-flash",)

def test_rate_limit_uses_same_key_last_valid_snapshot(local_temp_dir):
    snapshot_path = local_temp_dir / "snapshot.json"

    def good_opener(req, timeout):
        return _Response(
            {
                "models": [
                    {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]}
                ]
            }
        )

    discover_remote_models("same-key", snapshot_path=snapshot_path, urlopen=good_opener)

    def rate_limited_opener(req, timeout):
        raise HTTPError(req.full_url, 429, "rate limited", {}, io.BytesIO(b"{}"))

    result = discover_remote_models("same-key", snapshot_path=snapshot_path, urlopen=rate_limited_opener)

    assert result.status == DISCOVERY_STATUS_OFFLINE_SNAPSHOT
    assert result.error_code == "rate_limited"
    assert result.available_model_ids == ("gemini-3.6-flash",)

def test_snapshot_isolated_by_api_key_and_contains_no_raw_key(local_temp_dir):
    snapshot_path = local_temp_dir / "snapshot.json"
    snapshot = ModelAvailabilitySnapshot(
        captured_at=123.0,
        api_key_fingerprint="",
        records=(),
    ).with_api_key("secret-key")
    save_availability_snapshot(snapshot_path, snapshot)

    raw = snapshot_path.read_text(encoding="utf-8")
    assert "secret-key" not in raw
    assert load_availability_snapshot(snapshot_path, "secret-key") is not None
    assert load_availability_snapshot(snapshot_path, "other-key") is None


def test_malformed_snapshot_is_ignored(local_temp_dir):
    snapshot_path = local_temp_dir / "snapshot.json"
    snapshot_path.write_text("{not-json", encoding="utf-8")

    assert load_availability_snapshot(snapshot_path, "secret-key") is None


def test_fetch_invalid_payload_fails_closed_for_discovery(local_temp_dir):
    def opener(req, timeout):
        return _Response({"models": {"not": "a-list"}})

    result = discover_remote_models("key", snapshot_path=local_temp_dir / "snapshot.json", urlopen=opener)

    assert result.status == DISCOVERY_STATUS_UNVERIFIED
    assert result.verified is False
    assert result.available_model_ids == ()


def test_static_catalog_remains_fail_open_for_routing_when_unverified():
    result = type("Result", (), {"status": DISCOVERY_STATUS_UNVERIFIED, "available_model_ids": ()})()

    selected = filter_catalog_for_availability(MODEL_CATALOG, result)

    assert {spec.model_id for spec in selected} == {spec.model_id for spec in MODEL_CATALOG}


def test_verified_snapshot_filters_remote_catalog_but_keeps_local_model():
    result = type(
        "Result",
        (),
        {"status": "verified", "available_model_ids": ("gemini-3.6-flash",)},
    )()

    selected = filter_catalog_for_availability(MODEL_CATALOG, result)
    selected_ids = {spec.model_id for spec in selected}

    assert selected_ids == {"gemma-3-4b-it-local", "gemini-3.6-flash"}

def test_filter_model_choices_preserves_current_unavailable_model():
    from remote_model_discovery import (
        DISCOVERY_STATUS_VERIFIED,
        ModelDiscoveryResult,
        filter_model_choices_for_availability,
    )

    choices = (
        ("Local", "gemma-3-4b-it-local"),
        ("Available remote", "gemma-4-31b-it"),
        ("Unavailable remote", "gemini-2.5-pro"),
    )
    result = ModelDiscoveryResult(
        status=DISCOVERY_STATUS_VERIFIED,
        available_model_ids=("gemma-4-31b-it",),
        verified=True,
    )

    filtered = filter_model_choices_for_availability(
        choices,
        result,
        model_catalog=MODEL_CATALOG,
        current_model="gemini-2.5-pro",
    )

    assert filtered == (
        ("Local", "gemma-3-4b-it-local"),
        ("Available remote", "gemma-4-31b-it"),
        ("Unavailable remote", "gemini-2.5-pro"),
    )
