from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "cloudhime_dependency_licenses",
    ROOT / "packaging" / "collect_dependency_licenses.py",
)
assert _SPEC is not None and _SPEC.loader is not None
collector = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(collector)


def _distribution(
    site: Path,
    *,
    name: str = "sample-pkg",
    version: str = "1.2.3",
    files: dict[str, bytes] | None = None,
    license_file: str = "LICENSE",
):
    dist_info = site / f"sample_pkg-{version}.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\n"
        f"License: MIT License\nLicense-Expression: MIT\nLicense-File: {license_file}\n",
        encoding="utf-8",
    )
    if files is None:
        files = {f"{dist_info.name}/licenses/LICENSE": b"MIT\n"}
    record_paths = []
    for relative, data in files.items():
        path = site / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        record_paths.append(relative)
    with (dist_info / "RECORD").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows((path, "", "") for path in record_paths)
    return importlib.metadata.PathDistribution(dist_info)


def _report(path: Path, *, name: str = "sample-pkg", version: str = "1.2.3") -> Path:
    path.write_text(json.dumps({"install": [{"metadata": {"name": name, "version": version}}]}), encoding="utf-8")
    return path


def test_requires_exact_installed_version(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist = _distribution(site)
    with pytest.raises(collector.LicenseCollectionError, match="found 0"):
        collector.collect_dependency_licenses(
            _report(tmp_path / "report.json", version="1.2.4"),
            tmp_path / "out",
            distributions=[dist],
        )


def test_rejects_case_insensitive_license_destination_collisions(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist = _distribution(site, files={
        "sample_pkg-1.2.3.dist-info/licenses/LICENSE": b"first license",
        "sample_pkg-1.2.3.dist-info/licenses/license": b"second license",
    })
    with pytest.raises(collector.LicenseCollectionError, match="case-insensitive collision"):
        collector.collect_dependency_licenses(
            _report(tmp_path / "report.json"), tmp_path / "out", distributions=[dist]
        )


def test_records_missing_license_evidence_instead_of_claiming_complete(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist = _distribution(site, files={})
    manifest = collector.collect_dependency_licenses(
        _report(tmp_path / "report.json"), tmp_path / "out", distributions=[dist]
    )
    assert "License-File missing from RECORD: LICENSE" in manifest["packages"][0]["missing"]
    assert "No license files found in RECORD or License-File metadata" in manifest["packages"][0]["missing"]
    assert manifest["packages"][0]["missing_license"] is True
    assert manifest["packages"][0]["files"] == []


def test_rejects_record_path_traversal(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    outside = tmp_path / "outside" / "LICENSE"
    outside.parent.mkdir()
    outside.write_bytes(b"must not be copied")
    dist = _distribution(site, files={"../outside/LICENSE": b"must not be copied"})
    with pytest.raises(collector.LicenseCollectionError, match="escapes installation root"):
        collector.collect_dependency_licenses(
            _report(tmp_path / "report.json"), tmp_path / "out", distributions=[dist]
        )
    assert not list((tmp_path / "out").rglob("LICENSE"))


def test_copies_original_bytes_and_hashes_with_static_supplements(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    raw = b"MIT license\r\n\xff\x00"
    dist = _distribution(
        site,
        files={f"sample_pkg-1.2.3.dist-info/licenses/LICENSE": raw},
    )
    supplements = tmp_path / "static"
    supplements.mkdir()
    supplement = b"user-provided text\n"
    (supplements / "THIRD_PARTY_NOTICE.txt").write_bytes(supplement)
    output = tmp_path / "out"
    manifest = collector.collect_dependency_licenses(
        _report(tmp_path / "report.json"),
        output,
        supplement_dir=supplements,
        distributions=[dist],
    )
    package_file = output / manifest["packages"][0]["files"][0]["output_path"]
    assert package_file.read_bytes() == raw
    assert manifest["packages"][0]["license"] == "MIT License"
    assert manifest["packages"][0]["license_expression"] == "MIT"
    assert manifest["packages"][0]["files"][0]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert (output / "supplements" / "THIRD_PARTY_NOTICE.txt").read_bytes() == supplement
    assert manifest["supplements"][0]["sha256"] == hashlib.sha256(supplement).hexdigest()
    assert manifest["legalCompliance"] == "not_assessed"
    assert manifest["reportSha256"] == hashlib.sha256((tmp_path / "report.json").read_bytes()).hexdigest()


def test_flags_qt_commercial_reference_as_missing_usable_license(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist_info = site / "sample_pkg-1.2.3.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.3\nName: sample-pkg\nVersion: 1.2.3\n"
        "License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only\n"
        "License-File: LicenseRef-Qt-Commercial.txt\n",
        encoding="utf-8",
    )
    relative = f"{dist_info.name}/licenses/LicenseRef-Qt-Commercial.txt"
    (dist_info / "licenses").mkdir()
    (site / relative).write_bytes(b"Commercial license reference only")
    with (dist_info / "RECORD").open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerow((relative, "", ""))
    dist = importlib.metadata.PathDistribution(dist_info)
    manifest = collector.collect_dependency_licenses(
        _report(tmp_path / "report.json"), tmp_path / "out", distributions=[dist]
    )
    package = manifest["packages"][0]
    assert package["files"]
    assert package["missing_usable_license"] is True
    assert package["missing_license"] is False


def test_rejects_license_file_header_traversal(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist = _distribution(site)
    metadata_path = site / "sample_pkg-1.2.3.dist-info" / "METADATA"
    metadata_path.write_text(
        metadata_path.read_text(encoding="utf-8") + "License-File: ../../outside/LICENSE\n",
        encoding="utf-8",
    )
    # PathDistribution reads metadata lazily, so rebuild it after changing METADATA.
    dist = importlib.metadata.PathDistribution(metadata_path.parent)
    with pytest.raises(collector.LicenseCollectionError, match="escapes installation root"):
        collector.collect_dependency_licenses(
            _report(tmp_path / "report.json"), tmp_path / "out", distributions=[dist]
        )


def test_license_file_metadata_collects_non_license_named_file(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    raw = b"license text under a neutral filename\x00"
    relative = "sample_pkg-1.2.3.dist-info/legal.txt"
    dist = _distribution(site, files={relative: raw}, license_file="legal.txt")
    report = _report(tmp_path / "report.json")
    output = tmp_path / "out"
    manifest = collector.collect_dependency_licenses(report, output, distributions=[dist])
    record = manifest["packages"][0]["files"][0]
    assert record["source_path"] == relative
    assert (output / record["output_path"]).read_bytes() == raw


def test_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist = _distribution(site)
    output = tmp_path / "out"
    output.mkdir()
    (output / "stale.txt").write_text("old release", encoding="utf-8")
    with pytest.raises(collector.LicenseCollectionError, match="must be empty"):
        collector.collect_dependency_licenses(
            _report(tmp_path / "report.json"), output, distributions=[dist]
        )


def test_rejects_output_or_parent_reparse_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist = _distribution(site)
    link = tmp_path / "link"
    link.mkdir()
    for reparse_path in (link.absolute(), (link / "out").absolute()):
        monkeypatch.setattr(
            collector,
            "_is_reparse_or_symlink",
            lambda path, target=reparse_path: path == target,
        )
        with pytest.raises(collector.LicenseCollectionError, match="symlink/reparse"):
            collector.collect_dependency_licenses(
                _report(tmp_path / "report.json"), link / "out", distributions=[dist]
            )


def test_rejects_overlapping_supplement_and_output(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    dist = _distribution(site)
    overlap = tmp_path / "licenses"
    overlap.mkdir()
    with pytest.raises(collector.LicenseCollectionError, match="must not overlap"):
        collector.collect_dependency_licenses(
            _report(tmp_path / "report.json"),
            overlap,
            supplement_dir=overlap,
            distributions=[dist],
        )


def test_rejects_duplicate_canonical_report_names(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"install": [
            {"metadata": {"name": "sample_pkg", "version": "1.2.3"}},
            {"metadata": {"name": "sample-pkg", "version": "2.0"}},
        ]}),
        encoding="utf-8",
    )
    with pytest.raises(collector.LicenseCollectionError, match="duplicate canonical"):
        collector.collect_dependency_licenses(report, tmp_path / "out", distributions=[])
