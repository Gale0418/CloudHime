"""Regression tests for the single source of truth used by CI test groups."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "ci" / "test_groups.json"


def _load_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _repository_test_files() -> set[str]:
    return {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests").glob("test_*.py")
    }


def test_ci_inventory_assigns_every_test_file_exactly_once():
    inventory = _load_inventory()
    groups = inventory.get("groups")
    assert isinstance(groups, list) and groups

    group_names = [group.get("name") for group in groups]
    assert all(isinstance(name, str) and name for name in group_names)
    assert len(group_names) == len(set(group_names))

    assignments: list[str] = []
    for group in groups:
        files = group.get("test_files")
        assert isinstance(files, list), group.get("name")
        assert all(isinstance(path, str) for path in files), group.get("name")
        assignments.extend(files)

    assert len(assignments) == len(set(assignments)), "a test file is assigned more than once"
    assert set(assignments) == _repository_test_files()


def test_ci_inventory_points_only_to_existing_test_files():
    inventory = _load_inventory()
    assigned = {
        path
        for group in inventory["groups"]
        for path in group["test_files"]
    }
    assert all((ROOT / path).is_file() for path in assigned)
    assert all(path.startswith("tests/test_") and path.endswith(".py") for path in assigned)

def test_ci_matrix_runner_splits_paths_on_whitespace():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "-split '\\s+'" in workflow
    assert "-split '\\\\s+'" not in workflow
