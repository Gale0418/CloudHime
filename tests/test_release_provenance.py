from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "cloudhime_release_provenance", ROOT / "packaging" / "release_provenance.py"
)
assert _SPEC is not None and _SPEC.loader is not None
provenance = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(provenance)


def _item(name: str, version: str, requested: bool, digest: str, *, requires_dist: list[str] | None = None) -> dict:
    return {
        "download_info": {
            "url": f"https://files.example.test/{name}-{version}-py3-none-any.whl",
            "archive_info": {"hashes": {"sha256": digest}},
        },
        "requested": requested,
        "metadata": {
            "name": name,
            "version": version,
            "license_expression": "MIT",
            "requires_dist": requires_dist or [],
        },
    }


def _report(items: list[dict]) -> dict:
    return {
        "version": "1",
        "pip_version": "26.0",
        "environment": {
            "implementation_name": "cpython",
            "python_version": "3.10.14",
            "sys_platform": "win32",
            "platform_machine": "AMD64",
        },
        "install": items,
    }


def _write_source_evidence(root: Path, *, include_transitive: bool = False) -> tuple[Path, Path, Path, Path]:
    report = root / "report.json"
    requirements = root / "requirements.txt"
    lock = root / "requirements-lock-win-amd64-py310.txt"
    sbom = root / "sbom.cdx.json"
    items = [_item("alpha-pkg", "1.0.0", True, "a" * 64, requires_dist=["beta-pkg>=2"])]
    lock_lines = ["alpha-pkg==1.0.0 --hash=sha256:" + "a" * 64]
    if include_transitive:
        items.append(_item("beta-pkg", "2.0.0", True, "b" * 64))
        lock_lines.append("beta-pkg==2.0.0 --hash=sha256:" + "b" * 64)
    value = _report(items)
    report.write_text(json.dumps(value), encoding="utf-8")
    requirements.write_text("alpha-pkg==1.0.0\n", encoding="utf-8")
    lock.write_text("\n".join(lock_lines) + "\n", encoding="utf-8")
    lock_requirements = {name: entry["version"] for name, entry in provenance.contract.read_lock(lock).items()}
    canonical = provenance.contract._canonical_with_items(value, lock_requirements)
    sbom.write_text(json.dumps(provenance.contract.build_sbom(canonical)), encoding="utf-8")
    return report, requirements, lock, sbom


def test_stage_then_verify_is_self_contained_and_target_bound(tmp_path: Path):
    report, requirements, lock, sbom = _write_source_evidence(tmp_path)
    output = tmp_path / "provenance"

    provenance.stage(report, requirements, lock, sbom, output)
    manifest = provenance.verify(output)

    assert manifest["schema_version"] == 1
    assert manifest["target"] == {"python": "3.10", "platform": "windows", "architecture": "x64"}
    assert {entry["path"] for entry in manifest["files"]} == set(provenance.REQUIRED_FILES) - {"release-provenance.json"}
    assert not any(str(tmp_path) in json.dumps(entry) for entry in manifest["files"])


def test_stage_and_verify_accept_lock_graph_when_all_lock_entries_are_requested(tmp_path: Path):
    report, requirements, lock, sbom = _write_source_evidence(tmp_path, include_transitive=True)
    output = tmp_path / "provenance"

    provenance.stage(report, requirements, lock, sbom, output)
    manifest = provenance.verify(output)

    assert {entry["path"] for entry in manifest["files"]} == set(provenance.REQUIRED_FILES) - {"release-provenance.json"}


@pytest.mark.parametrize("path_name, content", [
    ("requirements.txt", "alpha-pkg==9.9.9\n"),
    ("requirements-lock-win-amd64-py310.txt", "alpha-pkg==9.9.9 --hash=sha256:" + "a" * 64 + "\n"),
])
def test_stage_rejects_direct_or_lock_drift(tmp_path: Path, path_name: str, content: str):
    report, requirements, lock, sbom = _write_source_evidence(tmp_path, include_transitive=True)
    (tmp_path / path_name).write_text(content, encoding="utf-8")

    with pytest.raises(provenance.ProvenanceError):
        provenance.stage(report, requirements, lock, sbom, tmp_path / "provenance")


def test_stage_rejects_symlink_output_before_copying(tmp_path: Path):
    report, requirements, lock, sbom = _write_source_evidence(tmp_path)
    external_target = tmp_path / "external-target"
    external_target.mkdir()
    output = tmp_path / "provenance"
    try:
        os.symlink(external_target, output, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(provenance.ProvenanceError, match="must not be a symlink"):
        provenance.stage(report, requirements, lock, sbom, output)

    assert list(external_target.iterdir()) == []


@pytest.mark.parametrize("url", [
    "https://user:password@files.example.test/alpha.whl",
    "https://files.example.test/alpha.whl?token=secret",
    "https://files.example.test/alpha.whl#fragment",
])
def test_stage_rejects_pip_report_download_urls_with_credentials_or_tokens(tmp_path: Path, url: str):
    report, requirements, lock, sbom = _write_source_evidence(tmp_path)
    data = json.loads(report.read_text(encoding="utf-8"))
    data["install"][0]["download_info"]["url"] = url
    report.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(provenance.ProvenanceError, match="download URL"):
        provenance.stage(report, requirements, lock, sbom, tmp_path / "provenance")


@pytest.mark.parametrize("mutation", ["missing", "extra", "tamper"])
def test_verify_fails_closed_for_missing_extra_or_tampered_evidence(tmp_path: Path, mutation: str):
    report, requirements, lock, sbom = _write_source_evidence(tmp_path)
    output = tmp_path / "provenance"
    provenance.stage(report, requirements, lock, sbom, output)
    if mutation == "missing":
        (output / "requirements.txt").unlink()
    elif mutation == "extra":
        (output / "unexpected.txt").write_text("no", encoding="utf-8")
    else:
        (output / "production-sbom.cdx.json").write_text("{}", encoding="utf-8")

    with pytest.raises(provenance.ProvenanceError):
        provenance.verify(output)


def test_verify_rejects_report_target_drift(tmp_path: Path):
    report, requirements, lock, sbom = _write_source_evidence(tmp_path)
    data = json.loads(report.read_text(encoding="utf-8"))
    data["environment"]["platform_machine"] = "x86"
    report.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(provenance.ProvenanceError, match="AMD64"):
        provenance.stage(report, requirements, lock, sbom, tmp_path / "provenance")

def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _run_prepare_release_provenance(output: Path, fake_python: Path) -> subprocess.CompletedProcess[str]:
    powershell = _powershell()
    if powershell is None:
        pytest.skip("PowerShell is unavailable")
    return subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(ROOT / "packaging" / "prepare_release_provenance.ps1"),
            "-OutputDir",
            str(output),
            "-PythonCommand",
            str(fake_python),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def test_prepare_script_rejects_output_outside_build_before_python_or_delete(tmp_path: Path):
    output = tmp_path / "outside-build-output"
    output.mkdir()
    marker = output / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    fake_python = tmp_path / "fake-python.cmd"
    python_called = tmp_path / "python-called.txt"
    fake_python.write_text(
        f'@echo off\r\necho called>"{python_called}"\r\nexit /b 0\r\n',
        encoding="utf-8",
    )

    result = _run_prepare_release_provenance(output, fake_python)

    assert result.returncode != 0
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not python_called.exists()


def test_prepare_script_rejects_reparse_point_in_build_output_ancestry(tmp_path: Path):
    if _powershell() is None:
        pytest.skip("PowerShell is unavailable")
    build_root = ROOT / "build"
    build_root.mkdir(exist_ok=True)
    external = tmp_path / "external"
    external.mkdir()
    link = build_root / f"provenance-link-{tmp_path.name}"
    try:
        os.symlink(external, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks/junctions are unavailable: {exc}")
    marker = external / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    fake_python = tmp_path / "fake-python.cmd"
    python_called = tmp_path / "python-called.txt"
    fake_python.write_text(
        f'@echo off\r\necho called>"{python_called}"\r\nexit /b 0\r\n',
        encoding="utf-8",
    )
    try:
        result = _run_prepare_release_provenance(link / "provenance", fake_python)
    finally:
        link.unlink()

    assert result.returncode != 0
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not python_called.exists()