from __future__ import annotations

import json

import pytest

from knowledge_pack_store import (
    KnowledgePackStore,
    KnowledgePackValidationError,
    create_knowledge_pack_paths,
)
from settings_store import create_settings_paths


def test_pack_paths_live_under_appdata_not_install_directory(tmp_path):
    install_dir = tmp_path / "install"
    appdata_dir = tmp_path / "appdata"
    install_dir.mkdir()
    settings_paths = create_settings_paths(str(install_dir), str(appdata_dir))

    paths = create_knowledge_pack_paths(settings_paths)
    store = KnowledgePackStore(paths)
    store.save_pack("轉生重騎士", aliases=["重騎士轉生"])

    assert paths.root == appdata_dir / "CloudHime" / "knowledge_packs"
    assert paths.catalog_file.is_file()
    assert tuple(paths.root.glob("pack-*.json"))
    assert not (install_dir / "knowledge_packs").exists()
    assert not tuple(install_dir.rglob("pack-*.json"))


def test_store_persists_multiple_packs_and_one_active_revision(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    first = store.save_pack(
        "轉生重騎士",
        aliases=["重騎士轉生"],
        entries=[{"kind": "character", "name": "凱爾"}],
    )
    second = store.save_pack("Princess Synergy")

    reopened = KnowledgePackStore(root)
    assert {summary.title for summary in reopened.list_packs()} == {
        "轉生重騎士",
        "Princess Synergy",
    }
    assert reopened.active_pack() is None
    assert reopened.activate(first["pack_id"]) is True

    reopened = KnowledgePackStore(root)
    assert reopened.active_pack()["pack_id"] == first["pack_id"]
    assert reopened.active_pack()["revision"] == 1
    assert reopened.activate(second["pack_id"]) is True

    reopened = KnowledgePackStore(root)
    assert reopened.active_pack()["pack_id"] == second["pack_id"]


def test_update_creates_revision_without_implicitly_switching_active_pack(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    first = store.save_pack("轉生重騎士", entries=[{"name": "舊資料"}])
    assert KnowledgePackStore(root).activate(first["pack_id"]) is True

    updated = KnowledgePackStore(root).save_pack(
        "轉生重騎士",
        pack_id=first["pack_id"],
        entries=[{"name": "新資料"}],
    )

    reopened = KnowledgePackStore(root)
    assert updated["revision"] == 2
    assert reopened.get_pack(first["pack_id"])["revision"] == 2
    assert reopened.get_pack(first["pack_id"], 1)["entries"] == [{"name": "舊資料"}]
    assert reopened.active_pack()["revision"] == 1
    assert reopened.active_pack()["entries"] == [{"name": "舊資料"}]

    assert reopened.activate(first["pack_id"], 2) is True
    assert KnowledgePackStore(root).active_pack()["entries"] == [{"name": "新資料"}]


def test_missing_or_corrupt_catalog_fails_open(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)

    assert store.list_packs() == ()
    assert store.active_pack() is None

    root.mkdir()
    (root / "catalog.json").write_text("not-json", encoding="utf-8")
    reopened = KnowledgePackStore(root)
    assert reopened.list_packs() == ()
    assert reopened.active_pack() is None


def test_corrupt_pack_is_excluded_and_active_read_fails_open(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    saved = store.save_pack("轉生重騎士")
    assert KnowledgePackStore(root).activate(saved["pack_id"]) is True
    pack_path = next(root.glob("pack-*.json"))
    pack_path.write_text(json.dumps({"schema_version": 1, "pack_id": saved["pack_id"]}), encoding="utf-8")

    reopened = KnowledgePackStore(root)
    assert reopened.list_packs() == ()
    assert reopened.active_pack() is None


def test_invalid_title_and_pack_id_are_rejected(tmp_path):
    store = KnowledgePackStore(tmp_path / "packs")

    with pytest.raises(KnowledgePackValidationError, match="title"):
        store.save_pack("   ")
    with pytest.raises(KnowledgePackValidationError, match="id"):
        store.save_pack("作品", pack_id="../outside")

    assert not (tmp_path / "outside").exists()


def test_case_sensitive_pack_ids_have_distinct_files(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    upper = store.save_pack("大寫", pack_id="Alpha")
    lower = store.save_pack("小寫", pack_id="alpha")

    files = tuple(sorted(root.glob("pack-*.json")))
    assert len(files) == 2
    assert upper["pack_id"] != lower["pack_id"]
    assert KnowledgePackStore(root).get_pack("Alpha")["title"] == "大寫"
    assert KnowledgePackStore(root).get_pack("alpha")["title"] == "小寫"


def test_corrupt_catalog_does_not_reuse_existing_revision(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    first = store.save_pack("第一版", pack_id="Alpha")
    (root / "catalog.json").write_text("not-json", encoding="utf-8")

    second = KnowledgePackStore(root).save_pack("第二版", pack_id="Alpha")

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert KnowledgePackStore(root).get_pack("Alpha", 1)["title"] == "第一版"
    assert KnowledgePackStore(root).get_pack("Alpha", 2)["title"] == "第二版"


def test_clear_active_is_persistent(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    saved = store.save_pack("轉生重騎士")
    assert KnowledgePackStore(root).activate(saved["pack_id"]) is True

    KnowledgePackStore(root).clear_active()
    reopened = KnowledgePackStore(root)
    assert reopened.active_pack() is None
    assert reopened.list_packs()[0].title == "轉生重騎士"

def test_corrupt_catalog_recovers_valid_pack_files_before_saving(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    first = store.save_pack("First")
    second = store.save_pack("Second")
    (root / "catalog.json").write_text("{not-json", encoding="utf-8")

    third = KnowledgePackStore(root).save_pack("Third")

    reopened = KnowledgePackStore(root)
    assert {item.title for item in reopened.list_packs()} == {"First", "Second", "Third"}
    assert reopened.get_pack(first["pack_id"], first["revision"]) is not None
    assert reopened.get_pack(second["pack_id"], second["revision"]) is not None
    assert reopened.get_pack(third["pack_id"], third["revision"]) is not None
    assert reopened.active_pack() is None

def test_recovery_ignores_noncanonical_pack_filename(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    first = store.save_pack("First")
    second = store.save_pack("Second")
    canonical = next(path for path in root.glob("pack-*.json") if second["pack_id"].lower() in path.name.lower())
    canonical.rename(root / ("renamed-" + canonical.name))
    (root / "catalog.json").write_text("{not-json", encoding="utf-8")

    recovered = KnowledgePackStore(root).list_packs()

    assert {item.title for item in recovered} == {"First"}
    assert first["revision"] == 1
    assert second["revision"] == 1


def test_malformed_current_catalog_recovers_from_pack_files(tmp_path):
    root = tmp_path / "packs"
    store = KnowledgePackStore(root)
    saved = store.save_pack("Saved")
    (root / "catalog.json").write_text(
        '{"schema_version": 1, "packs": null, "active": null}',
        encoding="utf-8",
    )

    recovered = KnowledgePackStore(root).get_pack(saved["pack_id"], saved["revision"])

    assert recovered is not None
    assert recovered["title"] == "Saved"
def test_find_pack_for_title_matches_title_and_alias_casefold(tmp_path):
    store = KnowledgePackStore(tmp_path / "packs")
    saved = store.save_pack("Princess Synergy", aliases=["プリンセス・シナジー"])

    assert store.find_pack_for_title(" princess synergy ")["pack_id"] == saved["pack_id"]
    assert store.find_pack_for_title("プリンセス・シナジー")["title"] == "Princess Synergy"
    assert store.find_pack_for_title("unknown") is None

def test_find_pack_for_title_prefers_newest_matching_pack(tmp_path):
    store = KnowledgePackStore(tmp_path / "packs")
    old = store.save_pack("Princess Synergy", pack_id="old-pack", entries=[{"name": "old"}])
    newest = store.save_pack("Princess Synergy", pack_id="new-pack", entries=[{"name": "new"}])

    found = KnowledgePackStore(tmp_path / "packs").find_pack_for_title("Princess Synergy")

    assert old["pack_id"] != newest["pack_id"]
    assert found["pack_id"] == newest["pack_id"]
    assert found["entries"] == [{"name": "new"}]
