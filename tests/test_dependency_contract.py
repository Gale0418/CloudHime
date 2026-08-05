from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "cloudhime_dependency_contract",
    ROOT / "packaging" / "dependency_contract.py",
)
assert _SPEC is not None and _SPEC.loader is not None
contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(contract)


def _item(
    name: str,
    version: str,
    *,
    requested: bool,
    sha256: str,
    requires_dist: list[str] | None = None,
    license_expression: str | None = "MIT",
) -> dict:
    metadata = {
        "name": name,
        "version": version,
        "requires_dist": requires_dist or [],
    }
    if license_expression is not None:
        metadata["license_expression"] = license_expression
    return {
        "download_info": {
            "url": f"https://files.example.test/{name}-{version}-py3-none-any.whl",
            "archive_info": {"hashes": {"sha256": sha256}},
        },
        "requested": requested,
        "metadata": metadata,
    }


def _report() -> dict:
    return {
        "version": "1",
        "pip_version": "26.0",
        "environment": {"python_version": "3.10", "sys_platform": "win32"},
        "install": [
            _item(
                "alpha-pkg",
                "1.0.0",
                requested=True,
                sha256="a" * 64,
                requires_dist=["beta_pkg>=2"],
            ),
            _item(
                "beta_pkg",
                "2.0.0",
                requested=False,
                sha256="b" * 64,
            ),
        ],
    }


def _requirements(tmp_path: Path, content: str = "alpha-pkg==1.0.0\n") -> Path:
    path = tmp_path / "requirements.txt"
    path.write_text(content, encoding="utf-8")
    return path


def test_report_to_cyclonedx_is_deterministic_and_preserves_graph(tmp_path: Path):
    report = _report()
    canonical = contract._canonical_with_items(report, contract.read_requirements(_requirements(tmp_path)))
    sbom = contract.build_sbom(canonical)

    assert [item["name"] for item in sbom["components"]] == ["alpha-pkg", "beta_pkg"]
    assert sbom["specVersion"] == "1.6"
    assert sbom["dependencies"][0]["dependsOn"] == ["pkg:pypi/beta-pkg@2.0.0"]
    contract.verify_sbom(sbom, canonical)
    first = json.dumps(sbom, ensure_ascii=False, sort_keys=True)
    second = json.dumps(contract.build_sbom(canonical), ensure_ascii=False, sort_keys=True)
    assert first == second


def test_missing_wheel_hash_is_rejected(tmp_path: Path):
    report = _report()
    del report["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"]

    with pytest.raises(contract.ContractError, match="SHA-256"):
        contract._canonical_with_items(report, contract.read_requirements(_requirements(tmp_path)))


def test_direct_requirement_version_drift_is_rejected(tmp_path: Path):
    requirements = _requirements(tmp_path, "alpha-pkg==1.1.0\n")

    with pytest.raises(contract.ContractError, match="direct requirements mismatch"):
        contract._canonical_with_items(_report(), contract.read_requirements(requirements))


def test_missing_license_metadata_is_rejected(tmp_path: Path):
    report = _report()
    report["install"][1]["metadata"].pop("license_expression")
    report["install"][1]["metadata"]["classifier"] = []
    report["install"][1]["metadata"]["license"] = ""

    with pytest.raises(contract.ContractError, match="license metadata"):
        contract._canonical_with_items(report, contract.read_requirements(_requirements(tmp_path)))


def test_sbom_tampering_is_rejected(tmp_path: Path):
    canonical = contract._canonical_with_items(
        _report(), contract.read_requirements(_requirements(tmp_path))
    )
    sbom = contract.build_sbom(canonical)
    sbom["components"][0]["hashes"][0]["content"] = "c" * 64

    with pytest.raises(contract.ContractError, match="component drift"):
        contract.verify_sbom(sbom, canonical)


def test_ci_fails_fast_after_dependency_install_commands():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    start = workflow.index("  dependency-contract:")
    end = workflow.index("  msix-contract:", start)
    contract_job = workflow[start:end]

    for command in (
        "& $venvPython -m pip install --upgrade pip",
        "& $venvPython -m pip install --report $report -r requirements-ci.txt",
    ):
        position = contract_job.index(command) + len(command)
        next_command = contract_job.find("& $venvPython -m pip", position)
        boundary = next_command if next_command >= 0 else position + 180
        following = contract_job[position:boundary]
        assert "if ($LASTEXITCODE -ne 0)" in following

def test_ci_report_is_emitted_by_the_install_under_test():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    start = workflow.index("  dependency-contract:")
    end = workflow.index("  msix-contract:", start)
    contract_job = workflow[start:end]
    install_line = next(
        line.strip()
        for line in contract_job.splitlines()
        if "pip install --report $report -r requirements-ci.txt" in line
    )

    assert "--report $report" in install_line
    assert "--dry-run" not in install_line
    assert "--ignore-installed" not in install_line

def test_ci_declares_dependency_contract_gate():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "dependency-contract:" in workflow
    assert "-m pip check" in workflow
    assert "dependency_contract.py validate" in workflow
    assert "actions/upload-artifact@v4" in workflow