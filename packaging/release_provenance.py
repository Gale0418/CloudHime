"""Stage and verify self-contained production dependency provenance for releases."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit


_contract_spec = importlib.util.spec_from_file_location(
    "cloudhime_dependency_contract", Path(__file__).with_name("dependency_contract.py")
)
assert _contract_spec is not None and _contract_spec.loader is not None
contract = importlib.util.module_from_spec(_contract_spec)
sys.modules[_contract_spec.name] = contract
_contract_spec.loader.exec_module(contract)

SCHEMA_VERSION = 1
TARGET = {"python": "3.10", "platform": "windows", "architecture": "x64"}
REQUIRED_FILES = (
    "production-pip-report.json",
    "production-sbom.cdx.json",
    "requirements.txt",
    "requirements-lock-win-amd64-py310.txt",
    "release-provenance.json",
)
_PAYLOAD_SOURCES = {
    "production-pip-report.json": "report",
    "production-sbom.cdx.json": "sbom",
    "requirements.txt": "requirements",
    "requirements-lock-win-amd64-py310.txt": "lock",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProvenanceError(ValueError):
    """Raised when release dependency provenance cannot be trusted."""


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProvenanceError(f"JSON root must be an object: {path}")
    return value


def _validate_target_environment(report: dict) -> None:
    environment = report.get("environment")
    if not isinstance(environment, dict):
        raise ProvenanceError("pip report is missing environment")
    implementation = str(environment.get("implementation_name", environment.get("implementation", ""))).strip().lower()
    if implementation != "cpython":
        raise ProvenanceError("pip report environment is not CPython")
    version = str(environment.get("python_version", environment.get("python_full_version", ""))).strip()
    if not re.match(r"^3\.10(?:\.|$)", version):
        raise ProvenanceError("pip report environment is not Python 3.10")
    system = str(environment.get("sys_platform", environment.get("platform_system", ""))).strip().lower()
    if system not in {"win32", "windows"}:
        raise ProvenanceError("pip report environment is not Windows")
    machine = str(environment.get("platform_machine", environment.get("machine", ""))).strip().lower()
    if machine not in {"amd64", "x86_64"}:
        raise ProvenanceError("pip report environment is not AMD64")


def _validate_report_download_urls(report: dict) -> None:
    items = report.get("install")
    if not isinstance(items, list):
        return
    for index, item in enumerate(items):
        try:
            url = item["download_info"]["url"]
            parsed = urlsplit(url)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProvenanceError(f"pip report download URL is invalid at install[{index}]") from exc
        if not isinstance(url, str) or parsed.scheme not in {"http", "https"}:
            raise ProvenanceError(f"pip report download URL must be http(s) at install[{index}]")
        if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
            raise ProvenanceError(f"pip report download URL must not contain credentials, query, or fragment at install[{index}]")


def _validate_contract(report_path: Path, requirements_path: Path, lock_path: Path, sbom_path: Path) -> dict:
    report = _read_json(report_path)
    _validate_target_environment(report)
    _validate_report_download_urls(report)
    try:
        requirements = contract.read_requirements(requirements_path)
        lock = contract.read_lock(lock_path)
        lock_requirements = {name: entry["version"] for name, entry in lock.items()}
        canonical = contract._canonical_with_items(report, lock_requirements)
        contract.validate_direct_requirements(report, requirements)
        contract.validate_lock(report, lock)
        contract.verify_sbom(_read_json(sbom_path), canonical)
    except contract.ContractError as exc:
        raise ProvenanceError(f"dependency contract failed: {exc}") from exc
    return report


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exact_files(root: Path) -> set[str]:
    if root.is_symlink():
        raise ProvenanceError("provenance directory must not be a symlink")
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ProvenanceError("provenance must not contain symlinks")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    return actual


def _validate_manifest(manifest: dict, root: Path) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ProvenanceError("unsupported release provenance schema")
    if manifest.get("target") != TARGET:
        raise ProvenanceError("release provenance target drift")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != len(_PAYLOAD_SOURCES):
        raise ProvenanceError("release provenance manifest has an invalid file list")
    expected_paths = set(_PAYLOAD_SOURCES)
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}:
            raise ProvenanceError("release provenance manifest contains unexpected metadata")
        path = entry["path"]
        if not isinstance(path, str) or path not in expected_paths or path in seen:
            raise ProvenanceError("release provenance manifest contains an invalid file path")
        if os.path.isabs(path) or ".." in Path(path).parts:
            raise ProvenanceError("release provenance manifest contains an absolute or traversal path")
        size = entry["size"]
        digest = entry["sha256"]
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ProvenanceError(f"release provenance manifest has invalid size: {path}")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ProvenanceError(f"release provenance manifest has invalid SHA-256: {path}")
        candidate = root / path
        if not candidate.is_file() or candidate.is_symlink():
            raise ProvenanceError(f"release provenance evidence is missing: {path}")
        if candidate.stat().st_size != size or _hash_file(candidate) != digest:
            raise ProvenanceError(f"release provenance hash or size mismatch: {path}")
        seen.add(path)
    if seen != expected_paths:
        raise ProvenanceError("release provenance manifest file set mismatch")


def stage(report: Path, requirements: Path, lock: Path, sbom: Path, output: Path) -> dict:
    report, requirements, lock, sbom, output = map(Path, (report, requirements, lock, sbom, output))
    if output.is_symlink():
        raise ProvenanceError("provenance directory must not be a symlink")
    _validate_contract(report, requirements, lock, sbom)
    if output.exists() and any(output.iterdir()):
        raise ProvenanceError(f"refusing to overwrite non-empty provenance directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    sources = {"report": report, "requirements": requirements, "lock": lock, "sbom": sbom}
    for destination, source_name in _PAYLOAD_SOURCES.items():
        shutil.copyfile(sources[source_name], output / destination)
    entries = [
        {"path": path, "size": (output / path).stat().st_size, "sha256": _hash_file(output / path)}
        for path in sorted(_PAYLOAD_SOURCES)
    ]
    manifest = {"schema_version": SCHEMA_VERSION, "target": TARGET, "files": entries}
    (output / "release-provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    verify(output)
    return manifest


def verify(root: Path) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise ProvenanceError(f"provenance directory not found: {root}")
    actual = _exact_files(root)
    if actual != set(REQUIRED_FILES):
        raise ProvenanceError(f"release provenance file set mismatch: expected={sorted(REQUIRED_FILES)}, actual={sorted(actual)}")
    manifest = _read_json(root / "release-provenance.json")
    _validate_manifest(manifest, root)
    _validate_contract(
        root / "production-pip-report.json",
        root / "requirements.txt",
        root / "requirements-lock-win-amd64-py310.txt",
        root / "production-sbom.cdx.json",
    )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage_parser = commands.add_parser("stage")
    for name in ("report", "requirements", "lock", "sbom", "output"):
        stage_parser.add_argument(f"--{name}", required=True, type=Path)
    stage_parser.set_defaults(handler=lambda args: stage(args.report, args.requirements, args.lock, args.sbom, args.output))
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--provenance-dir", required=True, type=Path)
    verify_parser.set_defaults(handler=lambda args: verify(args.provenance_dir))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        args.handler(args)
        print(f"release provenance {args.command} ok")
        return 0
    except (OSError, ProvenanceError, json.JSONDecodeError) as exc:
        print(f"release provenance failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
