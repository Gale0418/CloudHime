"""Validate pip installation reports, target locks, and deterministic CycloneDX SBOMs.

This contract consumes pip's supported installation-report format at build/CI time,
validates target-specific hash locks, and fails closed on missing artifact hashes,
direct requirement drift, or incomplete license metadata.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

from packaging.markers import Marker
from packaging.requirements import InvalidRequirement, Requirement


CONTRACT_VERSION = 1
SUPPORTED_PIP_REPORT_VERSION = "1"
SUPPORTED_CYCLONEDX_VERSION = "1.6"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_LOCK_HASH_RE = re.compile(r"--hash=sha256:([0-9a-fA-F]{64})")


class ContractError(ValueError):
    """Raised when provenance evidence cannot be trusted."""


def normalize_name(value: str) -> str:
    name = value.strip().lower().replace("_", "-").replace(".", "-")
    name = re.sub(r"-+", "-", name)
    if not name or not _NAME_RE.match(name):
        raise ContractError(f"invalid distribution name: {value!r}")
    return name


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def read_requirements(path: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            raise ContractError(f"unsupported requirements option at {path}:{line_number}")
        line = line.split(" #", 1)[0].strip()
        line = re.sub(r"\s+--hash=sha256:[0-9a-fA-F]{64}", "", line).strip()
        match = re.match(
            r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*(?P<version>[^;\s#]+)"
            r"(?:\s*;.*)?$",
            line,
        )
        if not match:
            raise ContractError(f"requirements entry is not exact-pinned at {path}:{line_number}: {raw_line}")
        name = normalize_name(match.group("name"))
        version = match.group("version")
        if name in requirements:
            raise ContractError(f"duplicate requirement: {name}")
        requirements[name] = version
    if not requirements:
        raise ContractError(f"requirements file is empty: {path}")
    return requirements


def read_lock(path: Path) -> dict[str, dict[str, object]]:
    entries: dict[str, dict[str, object]] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(
            r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*(?P<version>[^\s#]+)",
            line,
        )
        if not match:
            raise ContractError(f"lock entry is not exact-pinned at {path}:{line_number}")
        hashes = {value.lower() for value in _LOCK_HASH_RE.findall(line)}
        if not hashes:
            raise ContractError(f"lock entry has no SHA-256 hash at {path}:{line_number}")
        name = normalize_name(match.group("name"))
        if name in entries:
            raise ContractError(f"duplicate lock distribution: {name}")
        entries[name] = {"version": match.group("version"), "hashes": hashes}
    if not entries:
        raise ContractError(f"lock file is empty: {path}")
    return entries


def validate_lock(report: dict, lock: dict[str, dict[str, object]]) -> None:
    items = report.get("install")
    if not isinstance(items, list) or not items:
        raise ContractError("pip report has no install entries")
    actual: dict[str, tuple[str, str]] = {}
    for item in items:
        component = _component(item)
        name = normalize_name(component["name"])
        if name in actual:
            raise ContractError(f"duplicate pip report distribution: {name}")
        actual[name] = (component["version"], component["hashes"][0]["content"])
    if set(actual) != set(lock):
        missing = sorted(set(lock) - set(actual))
        extra = sorted(set(actual) - set(lock))
        raise ContractError(f"lock mismatch: missing={missing}, extra={extra}")
    for name, (version, digest) in actual.items():
        expected = lock[name]
        if version != expected["version"] or digest not in expected["hashes"]:
            raise ContractError(f"lock mismatch: {name}")


def _marker_variables(marker: Marker) -> set[str]:
    """Return variables referenced by packaging's parsed marker tree."""
    variables: set[str] = set()

    def visit(nodes: object) -> None:
        if isinstance(nodes, list):
            for node in nodes:
                visit(node)
        elif isinstance(nodes, tuple):
            for node in (nodes[0], nodes[2]):
                if type(node).__name__ == "Variable":
                    variables.add(node.value)

    visit(marker._markers)
    return variables


def _marker_applies(marker: Marker | None, report_environment: object) -> bool:
    if marker is None:
        return True
    required_keys = _marker_variables(marker)
    # pip reports do not retain requested root extras, so their activation cannot
    # be proven. Omitting these edges avoids representing an unproven dependency.
    if "extra" in required_keys:
        return False
    if not isinstance(report_environment, dict):
        raise ContractError("pip report environment is required for marker dependencies")
    missing_keys = sorted(
        key for key in required_keys if not isinstance(report_environment.get(key), str)
    )
    if missing_keys:
        raise ContractError(
            "pip report environment is incomplete for marker dependencies: "
            + ", ".join(missing_keys)
        )
    environment = {key: report_environment[key] for key in required_keys}
    return marker.evaluate(environment=environment)


def validate_marker_dependencies(report: dict) -> None:
    """Require pip reports to resolve dependencies selected by target markers."""
    items = report.get("install")
    if not isinstance(items, list) or not items:
        raise ContractError("pip report has no install entries")

    resolved: set[str] = set()
    missing_dependencies: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise ContractError("pip report install entry must be an object")
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise ContractError("pip report item is missing metadata")
        raw_name = metadata.get("name")
        if not isinstance(raw_name, str):
            raise ContractError("pip report item has invalid name")
        owner = normalize_name(raw_name)
        resolved.add(owner)
    for item in items:
        metadata = item["metadata"]
        owner = normalize_name(metadata["name"])
        requires_dist = metadata.get("requires_dist") or []
        if not isinstance(requires_dist, list):
            raise ContractError(f"invalid requires_dist metadata for {owner}")
        for raw_requirement in requires_dist:
            if not isinstance(raw_requirement, str):
                raise ContractError(f"invalid requires_dist entry for {owner}")
            try:
                requirement = Requirement(raw_requirement)
            except InvalidRequirement as exc:
                raise ContractError(f"invalid requires_dist entry for {owner}: {raw_requirement!r}") from exc
            if requirement.marker is not None and _marker_applies(
                requirement.marker, report.get("environment")
            ):
                dependency = normalize_name(requirement.name)
                if dependency not in resolved:
                    missing_dependencies.append(f"{owner} -> {dependency} ({raw_requirement})")
    if missing_dependencies:
        raise ContractError(
            "resolved marker dependencies missing from pip report: "
            + "; ".join(sorted(missing_dependencies))
        )


def validate_direct_requirements(report: dict, requirements: dict[str, str]) -> None:
    items = report.get("install")
    if not isinstance(items, list) or not items:
        raise ContractError("pip report has no install entries")
    resolved = {}
    for item in items:
        component = _component(item)
        resolved[normalize_name(component["name"])] = component["version"]
    missing = sorted(set(requirements) - set(resolved))
    mismatched = sorted(
        name for name in set(requirements) & set(resolved)
        if requirements[name] != resolved[name]
    )
    if missing or mismatched:
        raise ContractError(
            f"direct requirements mismatch: missing={missing}, version_mismatch={mismatched}"
        )

def render_lock(report: dict) -> str:
    validate_marker_dependencies(report)
    items = report.get("install")
    if not isinstance(items, list) or not items:
        raise ContractError("pip report has no install entries")
    components = [_component(item) for item in items]
    components.sort(key=lambda value: normalize_name(value["name"]))
    lines = ["# Generated from pip installation report; target artifact hashes are required."]
    for component in components:
        digest = component["hashes"][0]["content"]
        lines.append(f"{component['name']}=={component['version']} --hash=sha256:{digest}")
    return "\n".join(lines) + "\n"

def _sha256(item: dict, name: str) -> str:
    try:
        hashes = item["download_info"]["archive_info"]["hashes"]
        value = hashes["sha256"]
    except (KeyError, TypeError) as exc:
        raise ContractError(f"missing wheel SHA-256 for {name}") from exc
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ContractError(f"invalid wheel SHA-256 for {name}")
    return value.lower()


def _download_url(item: dict, name: str) -> str:
    try:
        url = item["download_info"]["url"]
    except (KeyError, TypeError) as exc:
        raise ContractError(f"missing download URL for {name}") from exc
    if not isinstance(url, str) or urlsplit(url).scheme not in {"https", "http"}:
        raise ContractError(f"download URL must be http(s) for {name}")
    return url


def _license_decl(metadata: dict, name: str) -> dict:
    expression = metadata.get("license_expression")
    if isinstance(expression, str) and expression.strip():
        return {"expression": expression.strip()}
    license_name = metadata.get("license")
    if isinstance(license_name, str) and license_name.strip():
        return {"license": {"name": license_name.strip()}}
    classifiers = metadata.get("classifier") or []
    license_classifiers = [
        value.split(" :: ", 2)[-1].strip()
        for value in classifiers
        if isinstance(value, str) and value.startswith("License ::")
    ]
    if license_classifiers:
        return {"license": {"name": license_classifiers[0]}}
    raise ContractError(f"missing license metadata for {name}")


def _dependency_names(metadata: dict, report_environment: object) -> list[str]:
    names: set[str] = set()
    for raw in metadata.get("requires_dist") or []:
        if not isinstance(raw, str):
            continue
        try:
            requirement = Requirement(raw)
        except InvalidRequirement:
            continue
        if _marker_applies(requirement.marker, report_environment):
            names.add(normalize_name(requirement.name))
    return sorted(names)


def _component(item: dict) -> dict:
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        raise ContractError("pip report item is missing metadata")
    raw_name = metadata.get("name")
    version = metadata.get("version")
    if not isinstance(raw_name, str) or not isinstance(version, str) or not version.strip():
        raise ContractError("pip report item has invalid name or version")
    name = normalize_name(raw_name)
    url = _download_url(item, name)
    purl = f"pkg:pypi/{quote(name, safe='.-_')}@{quote(version, safe='.-_+')}"
    requested = bool(item.get("requested", False))
    component = {
        "bom-ref": purl,
        "type": "library",
        "name": raw_name,
        "version": version,
        "scope": "required",
        "purl": purl,
        "hashes": [{"alg": "SHA-256", "content": _sha256(item, name)}],
        "licenses": [_license_decl(metadata, name)],
        "properties": [
            {"name": "cloudhime:requested", "value": "true" if requested else "false"},
            {"name": "cloudhime:download-url", "value": url},
        ],
    }
    return component


def canonical_report(report: dict, requirements: dict[str, str]) -> dict:
    if report.get("version") != SUPPORTED_PIP_REPORT_VERSION:
        raise ContractError(f"unsupported pip report version: {report.get('version')!r}")
    validate_marker_dependencies(report)
    items = report.get("install")
    if not isinstance(items, list) or not items:
        raise ContractError("pip report has no install entries")

    components: dict[str, dict] = {}
    requested: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ContractError("pip report install entry must be an object")
        component = _component(item)
        name = normalize_name(component["name"])
        if name in components:
            raise ContractError(f"duplicate pip report distribution: {name}")
        components[name] = component
        if item.get("requested") is True:
            requested[name] = component["version"]

    if requested != requirements:
        missing = sorted(set(requirements) - set(requested))
        extra = sorted(set(requested) - set(requirements))
        mismatched = sorted(
            name for name in set(requirements) & set(requested)
            if requirements[name] != requested[name]
        )
        detail = f"missing={missing}, extra={extra}, version_mismatch={mismatched}"
        raise ContractError(f"pip report direct requirements mismatch: {detail}")

    return {
        "contract_version": CONTRACT_VERSION,
        "pip_report_version": report["version"],
        "pip_version": report.get("pip_version", "unknown"),
        "environment": report.get("environment", {}),
        "components": [components[name] for name in sorted(components)],
    }


def build_sbom(canonical: dict) -> dict:
    components = deepcopy(canonical["components"])
    refs = {normalize_name(component["name"]): component["bom-ref"] for component in components}
    dependencies = []
    for component in components:
        metadata_name = normalize_name(component["name"])
        # Dependency edges are taken from report metadata and limited to resolved components.
        dependency_refs = []
        for source in canonical.get("_report_items", []):
            metadata = source.get("metadata", {})
            if normalize_name(str(metadata.get("name", ""))) != metadata_name:
                continue
            dependency_refs = [
                refs[name]
                for name in _dependency_names(metadata, canonical.get("environment"))
                if name in refs
            ]
            break
        dependencies.append({"ref": component["bom-ref"], "dependsOn": sorted(set(dependency_refs))})
    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": SUPPORTED_CYCLONEDX_VERSION,
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "CloudHime"},
            "tools": [{"vendor": "CloudHime", "name": "dependency_contract", "version": str(CONTRACT_VERSION)}],
        },
        "components": components,
        "dependencies": dependencies,
    }


def _canonical_with_items(report: dict, requirements: dict[str, str]) -> dict:
    canonical = canonical_report(report, requirements)
    canonical["_report_items"] = report["install"]
    return canonical


def verify_sbom(sbom: dict, canonical: dict) -> None:
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != SUPPORTED_CYCLONEDX_VERSION:
        raise ContractError("unsupported CycloneDX SBOM format")
    expected = {item["bom-ref"]: item for item in canonical["components"]}
    actual_items = sbom.get("components")
    if not isinstance(actual_items, list):
        raise ContractError("SBOM components must be a list")
    actual = {item.get("bom-ref"): item for item in actual_items if isinstance(item, dict)}
    if set(actual) != set(expected):
        raise ContractError("SBOM component set does not match pip report")
    for ref, component in expected.items():
        if actual[ref] != component:
            raise ContractError(f"SBOM component drift: {ref}")
    expected_dependencies = build_sbom(canonical)["dependencies"]
    if sbom.get("dependencies") != expected_dependencies:
        raise ContractError("SBOM dependency graph drift")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_lock(args: argparse.Namespace) -> int:
    report = _read_json(Path(args.report))

    Path(args.output).write_text(render_lock(report), encoding="utf-8")
    print(f"hash lock generated: {Path(args.output)}")
    return 0

def command_validate(args: argparse.Namespace) -> int:
    report = _read_json(Path(args.report))
    requirements = read_requirements(Path(args.requirements))
    canonical = _canonical_with_items(report, requirements)
    if args.direct_requirements:
        validate_direct_requirements(report, read_requirements(Path(args.direct_requirements)))
    if args.lock:
        validate_lock(report, read_lock(Path(args.lock)))
    if args.sbom_output:
        write_json(Path(args.sbom_output), build_sbom(canonical))
    print(f"dependency contract ok: {len(canonical['components'])} components")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    report = _read_json(Path(args.report))
    requirements = read_requirements(Path(args.requirements))
    canonical = _canonical_with_items(report, requirements)
    if args.direct_requirements:
        validate_direct_requirements(report, read_requirements(Path(args.direct_requirements)))
    if args.lock:
        validate_lock(report, read_lock(Path(args.lock)))
    verify_sbom(_read_json(Path(args.sbom)), canonical)
    print(f"dependency contract and SBOM ok: {len(canonical['components'])} components")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--report", required=True, type=Path)
    validate.add_argument("--requirements", required=True, type=Path)
    validate.add_argument("--sbom-output", type=Path)
    validate.add_argument("--lock", type=Path)
    validate.add_argument("--direct-requirements", type=Path)
    validate.set_defaults(handler=command_validate)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--report", required=True, type=Path)
    verify.add_argument("--requirements", required=True, type=Path)
    verify.add_argument("--sbom", required=True, type=Path)
    verify.add_argument("--lock", type=Path)
    verify.add_argument("--direct-requirements", type=Path)
    verify.set_defaults(handler=command_verify)
    lock_parser = subparsers.add_parser("lock")
    lock_parser.add_argument("--report", required=True, type=Path)
    lock_parser.add_argument("--output", required=True, type=Path)
    lock_parser.set_defaults(handler=command_lock)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"dependency contract failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
