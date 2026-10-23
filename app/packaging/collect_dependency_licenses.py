"""Collect license files for distributions in a pip installation report."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from packaging.utils import canonicalize_name


class LicenseCollectionError(ValueError):
    """Raised when the report or installed distribution evidence is unsafe."""


_LICENSE_NAME = re.compile(r"^(?:license(?:ref)?|licence|copying|notice|authors|copyright)(?:[._-].*)?$", re.I)
_OUTPUT_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")


def _read_report(path: Path) -> tuple[list[dict], str]:
    try:
        report_bytes = path.read_bytes()
        report = json.loads(report_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseCollectionError(f"cannot read pip report {path}: {exc}") from exc
    install = report.get("install") if isinstance(report, dict) else None
    if not isinstance(install, list):
        raise LicenseCollectionError("pip report must contain an install array")
    entries = []
    names = set()
    for index, item in enumerate(install):
        metadata = item.get("metadata") if isinstance(item, dict) else None
        name = metadata.get("name") if isinstance(metadata, dict) else None
        version = metadata.get("version") if isinstance(metadata, dict) else None
        if not isinstance(name, str) or not isinstance(version, str):
            raise LicenseCollectionError(f"install[{index}] is missing metadata.name/version")
        if not _OUTPUT_COMPONENT.fullmatch(canonicalize_name(name)) or not _OUTPUT_COMPONENT.fullmatch(version):
            raise LicenseCollectionError(f"install[{index}] has unsafe name/version for output paths")
        normalized_name = canonicalize_name(name)
        if normalized_name in names:
            raise LicenseCollectionError(f"duplicate canonical distribution name in pip report: {normalized_name}")
        names.add(normalized_name)
        entries.append({"name": name, "version": version})
    return entries, hashlib.sha256(report_bytes).hexdigest()


def _safe_relative(raw: str) -> PurePosixPath:
    # Wheel RECORD and License-File paths use POSIX separators; reject Windows
    # absolute/drive paths too so malformed metadata cannot escape on Windows.
    windows = PureWindowsPath(raw)
    posix = PurePosixPath(raw.replace("\\", "/"))
    if windows.is_absolute() or windows.drive or posix.is_absolute() or ".." in posix.parts:
        raise LicenseCollectionError(f"license path escapes installation root: {raw!r}")
    if not posix.parts or any(part in {"", "."} for part in posix.parts):
        raise LicenseCollectionError(f"invalid license path: {raw!r}")
    return posix


def _is_license_path(path: PurePosixPath) -> bool:
    return "licenses" in {part.casefold() for part in path.parts[:-1]} or bool(_LICENSE_NAME.match(path.name))


def _reject_case_collisions(paths: Iterable[str]) -> None:
    seen = set()
    for path in paths:
        key = path.casefold()
        if key in seen:
            raise LicenseCollectionError(f"case-insensitive collision in license destinations: {path}")
        seen.add(key)


def _matches_license_file(record_path: PurePosixPath, declared_path: PurePosixPath) -> bool:
    parts = tuple(part.casefold() for part in record_path.parts)
    declared = tuple(part.casefold() for part in declared_path.parts)
    if len(parts) < len(declared) or parts[-len(declared):] != declared:
        return False
    prefix = parts[:-len(declared)]
    return "licenses" in prefix or any(part.endswith(".dist-info") for part in prefix)


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if path.is_symlink():
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _reject_reparse_chain(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    for component in reversed(absolute.parents):
        if _is_reparse_or_symlink(component):
            raise LicenseCollectionError(f"{label} path contains symlink/reparse parent: {component}")
    if _is_reparse_or_symlink(absolute):
        raise LicenseCollectionError(f"{label} path is a symlink/reparse point: {absolute}")
    return absolute


def _prepare_output(output_dir: Path, supplement_dir: Path | None) -> tuple[Path, Path | None]:
    output = _reject_reparse_chain(output_dir, "output")
    supplement = None
    if supplement_dir is not None:
        supplement = _reject_reparse_chain(supplement_dir, "supplement")
        if not supplement.is_dir():
            raise LicenseCollectionError(f"supplement path is not a directory: {supplement}")
        supplement = supplement.resolve(strict=True)
        output_resolved = output.resolve(strict=False)
        if output_resolved == supplement or output_resolved in supplement.parents or supplement in output_resolved.parents:
            raise LicenseCollectionError("output and supplement directories must not overlap")
    if output.exists():
        if not output.is_dir():
            raise LicenseCollectionError(f"output path is not a directory: {output}")
        if next(output.iterdir(), None) is not None:
            raise LicenseCollectionError(f"output directory must be empty: {output}")
    return output, supplement


def _distribution_metadata(dist: importlib.metadata.Distribution) -> tuple[str | None, str | None]:
    metadata = dist.metadata
    return metadata.get("License"), metadata.get("License-Expression")


def _collect_one(
    entry: dict,
    distributions: Iterable[importlib.metadata.Distribution],
    output_root: Path,
) -> dict:
    name, version = entry["name"], entry["version"]
    wanted_name = canonicalize_name(name)
    matches = [
        dist for dist in distributions
        if canonicalize_name(dist.metadata.get("Name", "")) == wanted_name
        and dist.version == version
    ]
    if len(matches) != 1:
        raise LicenseCollectionError(
            f"expected exactly one installed {name}=={version}, found {len(matches)}"
        )
    dist = matches[0]
    installation_root = Path(dist.locate_file("")).resolve()
    declared: dict[str, PurePosixPath] = {}
    files = dist.files or ()
    record_paths = []
    for file in files:
        raw = str(file)
        relative = PurePosixPath(raw.replace("\\", "/"))
        record_paths.append((raw, relative))
        if _is_license_path(relative):
            # Validate RECORD entries before allowing them to become copy sources.
            safe = _safe_relative(raw)
            declared[safe.as_posix()] = safe
    missing_metadata_files = []
    for raw in dist.metadata.get_all("License-File", []):
        metadata_relative = _safe_relative(raw)
        matched = [
            _safe_relative(record_raw) for record_raw, record_path in record_paths
            if _matches_license_file(record_path, metadata_relative)
        ]
        if not matched:
            # License-File is relative to dist-info/licenses, not site-packages.
            # Never resolve it directly against the installation root.
            missing_metadata_files.append(raw)
        for record_path in matched:
            declared[record_path.as_posix()] = record_path

    package_folder = output_root / "packages" / f"{canonicalize_name(name)}-{version}"
    _reject_case_collisions(declared)
    copied, missing = [], []
    for raw, relative in sorted(declared.items(), key=lambda item: item[0].casefold()):
        source = Path(dist.locate_file(str(relative))).resolve()
        try:
            source.relative_to(installation_root)
        except ValueError as exc:
            raise LicenseCollectionError(f"license path resolves outside installation root: {raw!r}") from exc
        if not source.is_file():
            missing.append(raw)
            continue
        data = source.read_bytes()
        destination = package_folder.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        copied.append({
            "source_path": relative.as_posix(),
            "output_path": destination.relative_to(output_root).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    missing.extend(f"License-File missing from RECORD: {raw}" for raw in missing_metadata_files)
    if not declared:
        missing.append("No license files found in RECORD or License-File metadata")
    license_text, license_expression = _distribution_metadata(dist)
    missing_usable_license = any(
        PurePosixPath(item["source_path"]).name.casefold() == "licenseref-qt-commercial.txt"
        for item in copied
    )
    return {
        "name": name,
        "version": version,
        "license": license_text,
        "license_expression": license_expression,
        "files": copied,
        "missing": missing,
        "missing_license": bool(missing),
        "missing_usable_license": missing_usable_license,
    }


def _collect_supplements(source_root: Path | None, output_root: Path) -> list[dict]:
    if source_root is None:
        return []
    source_root = source_root.resolve(strict=True)
    _reject_case_collisions(
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*") if path.is_file()
    )
    result = []
    for source in sorted(source_root.rglob("*"), key=lambda path: path.as_posix().casefold()):
        if _is_reparse_or_symlink(source):
            raise LicenseCollectionError(f"supplement must be a regular file: {source}")
        if source.is_dir():
            continue
        if not source.is_file():
            raise LicenseCollectionError(f"supplement must be a regular file: {source}")
        resolved = source.resolve(strict=True)
        try:
            relative = resolved.relative_to(source_root)
        except ValueError as exc:
            raise LicenseCollectionError(f"supplement escapes its directory: {source}") from exc
        data = resolved.read_bytes()
        destination = output_root / "supplements" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        result.append({
            "source_path": relative.as_posix(),
            "output_path": destination.relative_to(output_root).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return result


def collect_dependency_licenses(
    report_path: Path,
    output_dir: Path,
    *,
    supplement_dir: Path | None = None,
    distributions: Iterable[importlib.metadata.Distribution] | None = None,
) -> dict:
    """Copy only license evidence for report distributions and static supplements."""
    entries, report_sha256 = _read_report(report_path)
    available = list(distributions if distributions is not None else importlib.metadata.distributions())
    output_dir, supplement_dir = _prepare_output(output_dir, supplement_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packages = [
        _collect_one(entry, available, output_dir)
        for entry in sorted(entries, key=lambda item: (canonicalize_name(item["name"]), item["version"]))
    ]
    supplements = _collect_supplements(supplement_dir, output_dir)
    manifest = {
        "schema_version": 1,
        "legalCompliance": "not_assessed",
        "reportSha256": report_sha256,
        "packages": packages,
        "supplements": supplements,
    }
    (output_dir / "license-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path, help="pip installation report JSON")
    parser.add_argument("--output", required=True, type=Path, help="license collection output directory")
    parser.add_argument("--supplement-dir", type=Path, help="optional static, user-provided license files")
    args = parser.parse_args(argv)
    try:
        manifest = collect_dependency_licenses(
            args.report, args.output, supplement_dir=args.supplement_dir
        )
    except (LicenseCollectionError, OSError) as exc:
        parser.error(str(exc))
    missing = sum(len(package["missing"]) for package in manifest["packages"])
    print(f"Collected {len(manifest['packages'])} packages; {missing} missing license entries.")
    return 1 if missing or any(p["missing_usable_license"] for p in manifest["packages"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
