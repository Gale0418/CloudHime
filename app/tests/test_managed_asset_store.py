from __future__ import annotations

import hashlib
import io
from pathlib import Path
import shutil
from threading import Event

import pytest

import managed_asset_store as store


TEST_ROOT = Path(__file__).with_name("_managed_asset_store_test_data")


class Response(io.BytesIO):
    def __init__(self, payload: bytes, status: int):
        super().__init__(payload)
        self.status = status


def _spec(name: str, payload: bytes) -> store.AssetSpec:
    return store.AssetSpec(name, f"https://example.invalid/{name}", hashlib.sha256(payload).hexdigest(), len(payload))


def _clean(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)
    if TEST_ROOT.is_dir() and not any(TEST_ROOT.iterdir()):
        TEST_ROOT.rmdir()


def test_ensure_skips_verified_assets_without_opening():
    payload = b"already-valid"
    spec = _spec("cached.bin", payload)
    root = TEST_ROOT / "skip"
    try:
        root.mkdir(parents=True)
        (root / spec.name).write_bytes(payload)
        calls = []
        progress = []
        result = store.ensure_managed_assets(
            root,
            (spec,),
            progress_callback=lambda phase, percent: progress.append((phase, percent)),
            minimum_free_bytes=0,
            opener=lambda request: calls.append(request),
        )
        assert result == (root / spec.name,)
        assert calls == []
        assert progress[-1] == ("verifying", 80)
    finally:
        _clean(root)


def test_download_resumes_with_http_range_206():
    payload = b"abcdefghij"
    spec = _spec("range.bin", payload)
    destination = TEST_ROOT / "range" / spec.name
    part = destination.with_suffix(destination.suffix + ".part")
    try:
        part.parent.mkdir(parents=True)
        part.write_bytes(payload[:4])
        seen_headers = []

        def opener(req):
            seen_headers.append(req.headers.get("Range"))
            return Response(payload[4:], 206)

        store.download_managed_asset(spec, destination, opener=opener)
        assert seen_headers == ["bytes=4-"]
        assert destination.read_bytes() == payload
        assert not part.exists()
    finally:
        _clean(destination.parent)


def test_download_range_fallback_200_rewrites_partial_file():
    payload = b"full-response"
    spec = _spec("fallback.bin", payload)
    destination = TEST_ROOT / "fallback" / spec.name
    part = destination.with_suffix(destination.suffix + ".part")
    try:
        part.parent.mkdir(parents=True)
        part.write_bytes(payload[:3])

        def opener(req):
            assert req.headers.get("Range") == "bytes=3-"
            return Response(payload, 200)

        store.download_managed_asset(spec, destination, opener=opener)
        assert destination.read_bytes() == payload
        assert not part.exists()
    finally:
        _clean(destination.parent)


def test_download_rejects_oversize_chunk_before_write():
    payload = b"abcdefgh"
    spec = _spec("oversize.bin", payload[:5])
    destination = TEST_ROOT / "oversize" / spec.name
    part = destination.with_suffix(destination.suffix + ".part")
    try:
        part.parent.mkdir(parents=True)
        part.write_bytes(payload[:2])
        with pytest.raises(ValueError, match="exceeds declared size"):
            store.download_managed_asset(
                spec,
                destination,
                opener=lambda req: Response(payload[2:], 206),
            )
        assert part.read_bytes() == payload[:2]
        assert part.stat().st_size <= spec.size
        assert not destination.exists()
    finally:
        _clean(destination.parent)


def test_ensure_counts_resumable_part_toward_disk_requirement(monkeypatch):
    payload = b"0123456789"
    spec = _spec("resume-space.bin", payload)
    root = TEST_ROOT / "resume-space"
    part = (root / spec.name).with_suffix((root / spec.name).suffix + ".part")
    calls = []

    class Usage:
        free = len(payload) - 4 + 5

    try:
        part.parent.mkdir(parents=True)
        part.write_bytes(payload[:4])
        monkeypatch.setattr(store.shutil, "disk_usage", lambda path: Usage())

        def opener(req):
            calls.append(req.headers.get("Range"))
            return Response(payload[4:], 206)

        result = store.ensure_managed_assets(
            root,
            (spec,),
            minimum_free_bytes=5,
            opener=opener,
        )
        assert result == (root / spec.name,)
        assert (root / spec.name).read_bytes() == payload
        assert calls == ["bytes=4-"]
    finally:
        _clean(root)

def test_bad_hash_is_rejected_without_promoting():
    payload = b"correct"
    spec = _spec("hash.bin", payload)
    destination = TEST_ROOT / "hash" / spec.name
    part = destination.with_suffix(destination.suffix + ".part")
    try:
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"old-promoted-file")
        with pytest.raises(ValueError):
            store.download_managed_asset(
                spec,
                destination,
                opener=lambda req: Response(b"wrong!!", 200),
            )
        assert destination.read_bytes() == b"old-promoted-file"
        assert part.exists()
        assert not store.verify_managed_asset(destination, spec)
    finally:
        _clean(destination.parent)


def test_cancel_during_chunk_leaves_part_without_promoting():
    payload = b"cancel-me"
    spec = _spec("cancel.bin", payload)
    destination = TEST_ROOT / "cancel" / spec.name
    part = destination.with_suffix(destination.suffix + ".part")
    cancel_event = Event()

    class CancellingResponse(Response):
        def read(self, size=-1):
            chunk = super().read(2)
            if chunk:
                cancel_event.set()
            return chunk

    try:
        with pytest.raises(store.AssetDownloadCancelled):
            store.download_managed_asset(
                spec,
                destination,
                cancel_event=cancel_event,
                opener=lambda req: CancellingResponse(payload, 200),
            )
        assert not destination.exists()
        assert part.exists()
    finally:
        _clean(destination.parent)


def test_ensure_rejects_insufficient_disk_space(monkeypatch):
    payload = b"123456"
    spec = _spec("space.bin", payload)
    root = TEST_ROOT / "space"

    class Usage:
        free = len(payload) + 4

    try:
        monkeypatch.setattr(store.shutil, "disk_usage", lambda path: Usage())
        with pytest.raises(store.InsufficientDiskSpaceError):
            store.ensure_managed_assets(root, (spec,), minimum_free_bytes=5)
    finally:
        _clean(root)


def test_progress_percent_is_monotonic_and_ends_at_80():
    payloads = (b"first-payload", b"second-payload-longer")
    specs = tuple(_spec(f"asset-{index}.bin", payload) for index, payload in enumerate(payloads))
    root = TEST_ROOT / "progress"
    progress = []

    def opener(req):
        name = Path(req.full_url).name
        index = int(name.split("-")[1].split(".")[0])
        return Response(payloads[index], 200)

    try:
        result = store.ensure_managed_assets(
            root,
            specs,
            progress_callback=lambda phase, percent: progress.append((phase, percent)),
            opener=opener,
            minimum_free_bytes=0,
        )
        assert result == tuple(root / spec.name for spec in specs)
        percentages = [percent for _, percent in progress]
        assert percentages == sorted(percentages)
        assert all(0 <= percent <= 80 for percent in percentages)
        assert progress[-1] == ("verifying", 80)
    finally:
        _clean(root)

def test_ensure_skips_disk_check_when_no_assets_are_missing(monkeypatch):
    payload = b"cached"
    spec = _spec("no-disk-check.bin", payload)
    root = TEST_ROOT / "no-disk-check"
    try:
        root.mkdir(parents=True)
        (root / spec.name).write_bytes(payload)
        monkeypatch.setattr(
            store.shutil,
            "disk_usage",
            lambda path: pytest.fail("disk usage should not be checked"),
        )

        assert store.ensure_managed_assets(
            root,
            (spec,),
            minimum_free_bytes=10**18,
        ) == (root / spec.name,)
    finally:
        _clean(root)


def test_ensure_skips_disk_check_when_required_bytes_are_zero(monkeypatch):
    spec = _spec("zero-size.bin", b"")
    root = TEST_ROOT / "zero-size"
    try:
        monkeypatch.setattr(
            store.shutil,
            "disk_usage",
            lambda path: pytest.fail("disk usage should not be checked"),
        )

        result = store.ensure_managed_assets(
            root,
            (spec,),
            minimum_free_bytes=10**18,
            opener=lambda request: Response(b"", 200),
        )

        assert result == (root / spec.name,)
        assert (root / spec.name).read_bytes() == b""
    finally:
        _clean(root)


@pytest.mark.parametrize(
    "names",
    [
        ("same.bin", "same.bin"),
        ("Case.bin", "case.bin"),
    ],
)
def test_manifest_rejects_conflicting_destinations(tmp_path, names):
    root = tmp_path / "assets"
    specs = tuple(_spec(name, b"x") for name in names)

    with pytest.raises(ValueError, match="destinations conflict"):
        store.ensure_managed_assets(root, specs, minimum_free_bytes=0)


def test_manifest_rejects_path_traversal(tmp_path):
    root = tmp_path / "assets"
    spec = _spec("../outside.bin", b"x")

    with pytest.raises(ValueError, match="escapes root"):
        store.ensure_managed_assets(root, (spec,), minimum_free_bytes=0)

    assert not (tmp_path / "outside.bin").exists()