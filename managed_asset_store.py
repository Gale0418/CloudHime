"""共用的受管資產下載、續傳與驗證核心。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ntpath
import os
from pathlib import Path
import shutil
from typing import Callable, Iterable
from urllib import request


ByteProgress = Callable[[int], None]
ProgressCallback = Callable[[str, int], None]
CHUNK_SIZE = 1024 * 1024
DEFAULT_MINIMUM_FREE_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class AssetSpec:
    name: str
    url: str
    sha256: str
    size: int


class AssetDownloadCancelled(RuntimeError):
    """下載被呼叫端取消。"""


class InsufficientDiskSpaceError(RuntimeError):
    """下載所需的磁碟空間不足。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_managed_asset(path: Path, spec: AssetSpec) -> bool:
    try:
        return (
            path.is_file()
            and path.stat().st_size == spec.size
            and _sha256(path) == spec.sha256.lower()
        )
    except OSError:
        return False


def _cancelled(cancel_event) -> bool:
    return cancel_event is not None and cancel_event.is_set()


def _raise_if_cancelled(cancel_event) -> None:
    if _cancelled(cancel_event):
        raise AssetDownloadCancelled("asset download cancelled")


def _response_status(response) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if getcode is not None else 200
    return int(status or 200)


def _default_opener(req):
    return request.urlopen(req, timeout=30)


def download_managed_asset(
    spec: AssetSpec,
    destination: Path,
    byte_progress: ByteProgress | None = None,
    cancel_event=None,
    opener=None,
) -> Path:
    """下載一個資產至暫存檔，驗證成功後以原子操作 promote。"""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    _raise_if_cancelled(cancel_event)

    existing = part.stat().st_size if part.is_file() else 0
    if existing == spec.size and verify_managed_asset(part, spec):
        _raise_if_cancelled(cancel_event)
        if byte_progress:
            byte_progress(spec.size)
        os.replace(part, destination)
        return destination
    if existing >= spec.size:
        existing = 0

    headers = {"User-Agent": "CloudHime/1.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    req = request.Request(spec.url, headers=headers)
    open_fn = opener or _default_opener
    response = open_fn(req)

    status = _response_status(response)
    append = existing > 0 and status == 206
    downloaded = existing if append else 0
    mode = "ab" if append else "wb"
    if byte_progress:
        byte_progress(downloaded)

    with response, part.open(mode) as stream:
        while True:
            _raise_if_cancelled(cancel_event)
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            _raise_if_cancelled(cancel_event)
            if downloaded + len(chunk) > spec.size:
                raise ValueError(
                    f"asset response exceeds declared size: {spec.name}"
                )
            stream.write(chunk)
            downloaded += len(chunk)
            if byte_progress:
                byte_progress(downloaded)

    _raise_if_cancelled(cancel_event)
    if part.stat().st_size != spec.size or not verify_managed_asset(part, spec):
        raise ValueError(f"asset verification failed: {spec.name}")
    _raise_if_cancelled(cancel_event)
    os.replace(part, destination)
    return destination


def _required_download_bytes(spec: AssetSpec, destination: Path) -> int:
    part = destination.with_suffix(destination.suffix + '.part')
    try:
        if not part.is_file():
            return spec.size
        part_size = part.stat().st_size
    except OSError:
        return spec.size
    if 0 <= part_size < spec.size:
        return spec.size - part_size
    return spec.size


def _resolve_manifest_destinations(
    root: Path,
    specs: tuple[AssetSpec, ...],
) -> tuple[Path, ...]:
    root_for_check = Path(root).resolve()
    root_key = ntpath.normcase(ntpath.normpath(os.fspath(root_for_check)))
    paths: list[Path] = []
    seen: dict[str, str] = {}

    for spec in specs:
        destination = Path(root) / spec.name
        resolved_destination = destination.resolve(strict=False)
        destination_key = ntpath.normcase(
            ntpath.normpath(os.fspath(resolved_destination))
        )
        try:
            common_root = ntpath.commonpath((root_key, destination_key))
        except ValueError:
            common_root = None
        if common_root != root_key or destination_key == root_key:
            raise ValueError(
                f"managed asset destination escapes root: {spec.name!r}"
            )
        previous_name = seen.get(destination_key)
        if previous_name is not None:
            raise ValueError(
                "managed asset destinations conflict: "
                f"{previous_name!r} and {spec.name!r}"
            )
        seen[destination_key] = spec.name
        paths.append(destination)
    return tuple(paths)


def ensure_managed_assets(
    root: Path,
    manifest: Iterable[AssetSpec],
    progress_callback: ProgressCallback | None = None,
    cancel_event=None,
    opener=None,
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
) -> tuple[Path, ...]:
    """確保 manifest 中所有資產存在，回傳依 manifest 順序排列的路徑。"""
    root = Path(root)
    specs = tuple(manifest)
    root.mkdir(parents=True, exist_ok=True)
    paths = _resolve_manifest_destinations(root, specs)
    valid = tuple(
        verify_managed_asset(path, spec)
        for spec, path in zip(specs, paths)
    )
    missing = tuple(
        (spec, path)
        for spec, path, is_valid in zip(specs, paths, valid)
        if not is_valid
    )
    required_bytes = sum(
        _required_download_bytes(spec, path)
        for spec, path in missing
    )
    if (
        missing
        and required_bytes > 0
        and shutil.disk_usage(root).free < required_bytes + minimum_free_bytes
    ):
        raise InsufficientDiskSpaceError(
            f"insufficient disk space for managed assets: "
            f"required={required_bytes + minimum_free_bytes}"
        )

    total = sum(spec.size for spec in specs)
    completed = sum(
        spec.size
        for spec, is_valid in zip(specs, valid)
        if is_valid
    )
    last_percent = 0

    def report_download(completed_bytes: int) -> None:
        nonlocal last_percent
        percent = min(80, int(completed_bytes * 80 / max(1, total)))
        percent = max(last_percent, percent)
        last_percent = percent
        if progress_callback:
            progress_callback("downloading", percent)

    _raise_if_cancelled(cancel_event)
    report_download(completed)

    for spec, path, is_valid in zip(specs, paths, valid):
        _raise_if_cancelled(cancel_event)
        if is_valid:
            continue
        download_managed_asset(
            spec,
            path,
            byte_progress=lambda current, base=completed, size=spec.size: report_download(
                base + min(current, size)
            ),
            cancel_event=cancel_event,
            opener=opener,
        )
        completed += spec.size
        report_download(completed)
    if progress_callback:
        progress_callback("verifying", 80)
    return paths
