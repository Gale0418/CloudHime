"""Verify installed production files against the exact wheels in a locked report."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import sysconfig
import configparser
from urllib.parse import unquote, urlsplit
import zipfile


def _name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _record_rows(text: str | None, label: str):
    if not text:
        raise ValueError(f"Missing wheel RECORD: {label}")
    rows = {}
    for row in csv.reader(text.splitlines()):
        if len(row) != 3 or not row[0] or (row[0] in rows and not _is_cache(row[0])):
            raise ValueError(f"Invalid or duplicate RECORD entry: {label}")
        rows.setdefault(row[0], (row[1], row[2]))
    return rows


def _digest(path: Path, label: str) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"Missing/unreadable wheel file: {label}") from exc
    return base64.urlsafe_b64encode(digest.digest()).decode("ascii").rstrip("=")


def _hash_recorded_file(path: Path, value: str, label: str) -> None:
    try:
        mode, expected = value.split("=", 1)
        if not mode or not expected:
            raise ValueError
        digest = hashlib.new(mode)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid RECORD hash: {label}") from exc
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"Missing/unreadable wheel file: {label}") from exc
    actual = base64.urlsafe_b64encode(digest.digest()).decode("ascii").rstrip("=")
    if actual != expected:
        raise ValueError(f"Wheel RECORD hash mismatch: {label}")


def _wheel_info(item, wheel_dir: Path):
    metadata = item["metadata"]
    try:
        download = item["download_info"]
        url = download["url"]
        expected_sha = download["archive_info"]["hashes"]["sha256"].lower()
        filename = unquote(PurePosixPath(urlsplit(url).path).name)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Missing trusted wheel URL/hash: {metadata['name']}") from exc
    if not filename.endswith(".whl") or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError(f"Invalid trusted wheel URL/hash: {metadata['name']}")
    wheel_path = wheel_dir / filename
    actual_sha = hashlib.sha256()
    try:
        with wheel_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                actual_sha.update(chunk)
    except OSError as exc:
        raise ValueError(f"Missing trusted wheel: {filename}") from exc
    if actual_sha.hexdigest() != expected_sha:
        raise ValueError(f"Trusted wheel SHA256 mismatch: {filename}")
    return metadata, filename, wheel_path


def _wheel_records(wheel_path: Path, metadata: dict, filename: str):
    try:
        archive = zipfile.ZipFile(wheel_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Invalid trusted wheel: {filename}") from exc
    with archive:
        names = archive.namelist()
        records = [name for name in names if name.endswith(".dist-info/RECORD") and ".data/" not in name]
        if len(records) != 1:
            raise ValueError(f"Wheel must contain exactly one dist-info/RECORD: {filename}")
        record_name = records[0]
        info_root = record_name.rsplit("/", 1)[0]
        try:
            dist_metadata = archive.read(info_root + "/METADATA").decode("utf-8")
            wheel_record = archive.read(record_name).decode("utf-8")
        except (KeyError, UnicodeDecodeError) as exc:
            raise ValueError(f"Incomplete trusted wheel metadata: {filename}") from exc
        fields = {}
        for line in dist_metadata.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields.setdefault(key.lower(), value.strip())
        if _name(fields.get("name", "")) != _name(metadata["name"]) or fields.get("version") != metadata["version"]:
            raise ValueError(f"Trusted wheel metadata does not match report: {metadata['name']}")
        entry_points = set()
        try:
            parser = configparser.ConfigParser()
            parser.read_string(archive.read(info_root + "/entry_points.txt").decode("utf-8"))
            entry_points = {key for key, _value in parser.items("console_scripts")} if parser.has_section("console_scripts") else set()
        except (KeyError, UnicodeDecodeError, configparser.Error):
            pass
        rows = _record_rows(wheel_record, filename)
        for relative in rows:
            parsed = PurePosixPath(relative)
            if parsed.is_absolute() or ".." in parsed.parts or "\\" in relative:
                raise ValueError(f"Unsafe path in wheel RECORD: {filename}/{relative}")
        archive_files = {name for name in names if not name.endswith("/")}
        unsigned_records = {info_root + "/RECORD.jws", info_root + "/RECORD.p7s"}
        if archive_files - set(rows) - unsigned_records:
            raise ValueError(f"Wheel contains files missing from RECORD: {filename}")
        script_tails = {}
        wheel_data = info_root.removesuffix(".dist-info") + ".data"
        for relative in rows:
            parts = PurePosixPath(relative).parts
            if len(parts) < 3 or parts[0] != wheel_data or parts[1] != "scripts":
                continue
            hash_value, _size = rows[relative]
            if not hash_value:
                continue
            try:
                mode, expected = hash_value.split("=", 1)
                whole_digest = hashlib.new(mode)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid RECORD hash: {filename}/{relative}") from exc
            with archive.open(relative) as stream:
                shebang = stream.readline()
                if shebang.rstrip(b"\r\n") not in {b"#!python", b"#!pythonw"}:
                    continue
                digest = hashlib.sha256()
                whole_digest.update(shebang)
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    whole_digest.update(chunk)
                actual = base64.urlsafe_b64encode(whole_digest.digest()).decode("ascii").rstrip("=")
                if actual != expected:
                    raise ValueError(f"Wheel RECORD hash mismatch: {filename}/{relative}")
                script_tails[relative] = digest.digest()
        return rows, info_root, entry_points, script_tails


def _wheel_path_for_install(dist, relative: str, info_root: str):
    """Map wheel paths to the install schemes pip uses for .data relocation."""
    parts = PurePosixPath(relative).parts
    wheel_data = info_root.removesuffix(".dist-info") + ".data"
    if len(parts) >= 3 and parts[0] == wheel_data and parts[1] in {"purelib", "platlib", "data", "scripts", "headers"}:
        scheme, tail = parts[1], Path(*parts[2:])
        if scheme == "headers":
            raise ValueError(f"Unsupported wheel .data/headers relocation: {relative}")
        if scheme in {"purelib", "platlib"}:
            return Path(dist.locate_file(tail)), scheme
        return Path(sysconfig.get_path(scheme)) / tail, scheme
    return Path(dist.locate_file(importlib.metadata.PackagePath(relative))), ""


def _installed_record_path(dist, path: Path, scheme: str, relative: str) -> str:
    if not scheme:
        return relative
    return Path(os.path.relpath(path, Path(dist.locate_file("")))).as_posix()


def _check_rewritten_script(path: Path, trusted_tail: bytes, label: str) -> None:
    expected = os.path.normcase(os.path.normpath(sys.executable))
    try:
        with path.open("rb") as stream:
            shebang = stream.readline().rstrip(b"\r\n")
            if not shebang.startswith(b"#!"):
                raise ValueError(f"Invalid pip-rewritten script shebang: {label}")
            actual = shebang[2:].decode("utf-8", errors="strict")
            if actual.startswith('"') and actual.endswith('"'):
                actual = actual[1:-1]
            if os.path.normcase(os.path.normpath(actual)) != expected:
                raise ValueError(f"Unexpected pip-rewritten script interpreter: {label}")
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"Missing/unreadable wheel file: {label}") from exc
    if digest.digest() != trusted_tail:
        raise ValueError(f"Rewritten script payload mismatch: {label}")


def _is_generated_entrypoint(relative: str, dist, entry_points: set[str]) -> bool:
    if not entry_points:
        return False
    target = Path(dist.locate_file(importlib.metadata.PackagePath(relative))).resolve()
    scripts = Path(sysconfig.get_path("scripts")).resolve()
    if target.parent != scripts:
        return False
    basename = target.name
    return any(basename in {name, name + ".exe"} for name in entry_points)


def _is_cache(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    return len(parts) >= 2 and parts[-2] == "__pycache__" and parts[-1].endswith(".pyc")


def verify(report: Path, wheel_dir: Path, *, distributions=None) -> dict[str, int]:
    installed = list(importlib.metadata.distributions() if distributions is None else distributions)
    checked = 0
    packages = json.loads(report.read_text(encoding="utf-8"))["install"]
    expected = {_name(item["metadata"]["name"]) for item in packages}
    opencv_variants = {"opencv-python", "opencv-python-headless", "opencv-contrib-python", "opencv-contrib-python-headless"}
    reported_opencv = expected & opencv_variants
    if len(reported_opencv) > 1:
        raise ValueError(f"Multiple OpenCV variants in report: {', '.join(sorted(reported_opencv))}")
    installed_opencv = {_name(dist.metadata["Name"]) for dist in installed} & opencv_variants
    if len(installed_opencv) > 1 or (reported_opencv and installed_opencv - reported_opencv):
        raise ValueError(f"Conflicting OpenCV namespace owner: {', '.join(sorted(installed_opencv))}")

    for item in packages:
        metadata, filename, wheel_path = _wheel_info(item, Path(wheel_dir))
        trusted, info_root, entry_points, script_tails = _wheel_records(wheel_path, metadata, filename)
        matches = [dist for dist in installed if _name(dist.metadata["Name"]) == _name(metadata["name"])]
        if len(matches) != 1 or matches[0].version != metadata["version"]:
            raise ValueError(f"Installed distribution does not match report: {metadata['name']}")
        dist = matches[0]
        installed_rows = _record_rows(dist.read_text("RECORD"), metadata["name"])
        # Wheel RECORD is authoritative. Installed RECORD may add only the small,
        # explicit set of files pip creates after unpacking.
        pip_generated = {f"{info_root}/INSTALLER", f"{info_root}/REQUESTED", f"{info_root}/direct_url.json"}
        trusted_paths = set(trusted)
        trusted_installed_paths = set(trusted_paths)
        for relative, (hash_value, _size) in trusted.items():
            if relative.endswith("/RECORD"):
                if hash_value:
                    raise ValueError(f"Wheel RECORD must be unhashed: {metadata['name']}/{relative}")
                continue
            if _is_cache(relative):
                continue
            if not hash_value:
                raise ValueError(f"Unhashed trusted wheel payload: {metadata['name']}/{relative}")
            path, scheme = _wheel_path_for_install(dist, relative, info_root)
            installed_entry = _installed_record_path(dist, path, scheme, relative)
            trusted_installed_paths.add(installed_entry)
            script_rewrite = scheme == "scripts" and relative in script_tails
            if script_rewrite:
                _check_rewritten_script(path, script_tails[relative], f"{metadata['name']}/{relative}")
            else:
                _hash_recorded_file(path, hash_value, f"{metadata['name']}/{relative}")
            if installed_entry not in installed_rows:
                raise ValueError(f"Installed RECORD omits trusted wheel file: {metadata['name']}/{relative}")
            installed_hash, _size = installed_rows[installed_entry]
            # pip rewrites only script launchers when it replaces their shebang.
            if script_rewrite:
                if not installed_hash:
                    raise ValueError(f"Unhashed installed script: {metadata['name']}/{relative}")
                _hash_recorded_file(path, installed_hash, f"{metadata['name']}/{relative}")
            elif installed_hash != hash_value:
                raise ValueError(f"Installed RECORD differs from trusted wheel: {metadata['name']}/{relative}")
            checked += 1

        for relative, (hash_value, _size) in installed_rows.items():
            if relative in trusted_installed_paths or _is_cache(relative):
                continue
            generated_entrypoint = _is_generated_entrypoint(relative, dist, entry_points)
            if relative not in pip_generated and not generated_entrypoint:
                raise ValueError(f"Unexpected installed RECORD file: {metadata['name']}/{relative}")
            if not hash_value:
                raise ValueError(f"Unhashed pip-generated metadata: {metadata['name']}/{relative}")
            path = Path(dist.locate_file(importlib.metadata.PackagePath(relative)))
            _hash_recorded_file(path, hash_value, f"{metadata['name']}/{relative}")
    return {"packages": len(packages), "hashedFiles": checked}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.report, args.wheel_dir)))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"Installed production dependency verification failed: {exc}\n")
