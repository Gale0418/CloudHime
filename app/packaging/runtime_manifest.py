"""Build and validate the bundled llama-server runtime manifest.

The manifest is generated from the exact runtime directory staged for PyInstaller.
It intentionally records only release files, not models or development archives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any


MANIFEST_NAME = "runtime-manifest.json"
SCHEMA_VERSION = 1
SERVER_PATH = "llama-server.exe"
SUPPORTED_ARCHITECTURE = "x64"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_files(runtime_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in runtime_dir.rglob("*")
            if path.is_file() and path.name != MANIFEST_NAME
        ),
        key=lambda path: path.relative_to(runtime_dir).as_posix(),
    )


def build_manifest(
    runtime_dir: str | Path,
    *,
    server_version: str,
    source_commit: str,
    backend: str,
    architecture: str,
) -> dict[str, Any]:
    root = Path(runtime_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"runtime directory not found: {root}")
    metadata = {
        "server_version": str(server_version).strip(),
        "source_commit": str(source_commit).strip(),
        "backend": str(backend).strip(),
        "architecture": str(architecture).strip(),
    }
    if not all(metadata.values()):
        raise ValueError("runtime manifest metadata must not be empty")
    if metadata["architecture"].casefold() != SUPPORTED_ARCHITECTURE:
        raise ValueError(
            f"unsupported runtime architecture: {metadata['architecture']!r}"
        )

    files = []
    for path in _runtime_files(root):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    if not any(item["path"].casefold() == SERVER_PATH.casefold() for item in files):
        raise ValueError("runtime manifest requires llama-server.exe")

    return {
        "schema_version": SCHEMA_VERSION,
        "runtime": "llama-server",
        "server": {
            "path": SERVER_PATH,
            "version": metadata["server_version"],
        },
        "build": {
            "source_commit": metadata["source_commit"],
            "backend": metadata["backend"],
            "architecture": metadata["architecture"],
        },
        "files": files,
    }


def validate_manifest(runtime_dir: str | Path, manifest: dict[str, Any]) -> None:
    root = Path(runtime_dir).resolve()
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported runtime manifest schema")
    if manifest.get("runtime") != "llama-server":
        raise ValueError("runtime manifest identifies an unexpected runtime")

    server = manifest.get("server")
    build = manifest.get("build")
    entries = manifest.get("files")
    if not isinstance(server, dict) or not str(server.get("version", "")).strip():
        raise ValueError("runtime manifest server version is missing")
    if not isinstance(build, dict) or not all(
        str(build.get(key, "")).strip()
        for key in ("source_commit", "backend", "architecture")
    ):
        raise ValueError("runtime manifest build metadata is incomplete")
    architecture = str(build["architecture"]).strip()
    if architecture.casefold() != SUPPORTED_ARCHITECTURE:
        raise ValueError(f"unsupported runtime architecture: {architecture!r}")
    if not isinstance(entries, list) or not entries:
        raise ValueError("runtime manifest files must be a non-empty list")

    expected: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("runtime manifest file entry must be an object")
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError("runtime manifest contains an invalid file path")
        normalized = Path(relative.replace("\\", "/"))
        if ".." in normalized.parts:
            raise ValueError("runtime manifest contains a path escape")
        key = normalized.as_posix()
        if key in expected:
            raise ValueError(f"runtime manifest contains duplicate file: {key}")
        if not isinstance(entry.get("size"), int) or entry["size"] < 0:
            raise ValueError(f"runtime manifest has invalid size: {key}")
        if (
            not isinstance(entry.get("sha256"), str)
            or len(entry["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in entry["sha256"].lower())
        ):
            raise ValueError(f"runtime manifest has invalid SHA-256: {key}")
        expected[key] = entry

    actual = {
        path.relative_to(root).as_posix(): path
        for path in _runtime_files(root)
    }
    if set(expected) != set(actual):
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise ValueError(
            f"runtime manifest file set mismatch; missing={missing}, unexpected={unexpected}"
        )

    for relative, entry in expected.items():
        path = actual[relative]
        actual_size = path.stat().st_size
        actual_hash = _sha256(path)
        if actual_size != entry["size"] or actual_hash.casefold() != entry["sha256"].casefold():
            raise ValueError(f"runtime manifest hash or size mismatch: {relative}")

    server_path = str(server.get("path", "")).replace("\\", "/")
    if server_path.casefold() != SERVER_PATH.casefold():
        raise ValueError("runtime manifest server path must be llama-server.exe")
    if server_path not in expected:
        raise ValueError("runtime manifest server path is not listed in files")


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)


def read_server_version(server_path: str | Path, *, timeout: float = 15.0) -> str:
    executable = Path(server_path)
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"llama-server --version timed out after {timeout:g}s") from exc
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace").strip()
    if result.returncode != 0 or not output:
        raise RuntimeError(
            f"llama-server --version failed with exit code {result.returncode}"
        )
    return output


def _positive_finite_timeout(value: str) -> float:
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError(
            "--version-timeout must be a finite number greater than zero"
        )
    return timeout

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--version-timeout", type=_positive_finite_timeout, default=15.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    server_version = read_server_version(
        args.runtime_dir / SERVER_PATH,
        timeout=args.version_timeout,
    )
    manifest = build_manifest(
        args.runtime_dir,
        server_version=server_version,
        source_commit=args.source_commit,
        backend=args.backend,
        architecture=args.architecture,
    )
    validate_manifest(args.runtime_dir, manifest)
    write_manifest(args.output, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
