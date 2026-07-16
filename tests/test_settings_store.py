import json

import pytest
import settings_store
from settings_store import (
    create_settings_paths,
    load_settings_data,
    normalize_settings_payload,
    save_settings_data,
)
from translation_registry import build_translation_registry, TranslationProviderRegistryConfig

def test_normalize_settings_payload_applies_local_multimodal_defaults():
    normalized = normalize_settings_payload({}, region_opacity=40)

    assert normalized["local_multimodal_enabled"] is False
    assert normalized["local_multimodal_base_url"] == "http://127.0.0.1:8080/v1"
    assert normalized["local_multimodal_model"] == ""
    assert normalized["local_multimodal_timeout_seconds"] == 20

def test_normalize_settings_payload_sanitizes_local_multimodal_timeout():
    invalid = normalize_settings_payload({"local_multimodal_timeout_seconds": "oops"}, region_opacity=40)
    low = normalize_settings_payload({"local_multimodal_timeout_seconds": -5}, region_opacity=40)
    high = normalize_settings_payload({"local_multimodal_timeout_seconds": 999}, region_opacity=40)

    assert invalid["local_multimodal_timeout_seconds"] == 20
    assert low["local_multimodal_timeout_seconds"] == 1
    assert high["local_multimodal_timeout_seconds"] == 300

def test_registry_registers_local_multimodal():
    config = TranslationProviderRegistryConfig(
        google_api_key="fake-key",
        local_multimodal_enabled=True,
        local_multimodal_model="gemma-3n-local"
    )
    registry = build_translation_registry(config)
    assert "local_multimodal" in registry._providers
    assert "gemma" in registry._providers
    assert "google" in registry._providers
def test_save_settings_writes_only_to_appdata(tmp_path):
    install_dir = tmp_path / "readonly-install"
    appdata_dir = tmp_path / "appdata"
    install_dir.mkdir()
    paths = create_settings_paths(str(install_dir), str(appdata_dir))

    save_settings_data(paths, {"language": "en"})

    assert json.loads((appdata_dir / "CloudHime" / "cloudhime_settings.json").read_text(encoding="utf-8")) == {
        "language": "en"
    }
    assert not (install_dir / "cloudhime_settings.json").exists()


def test_load_settings_keeps_legacy_file_as_read_only_migration_source(tmp_path):
    install_dir = tmp_path / "install"
    appdata_dir = tmp_path / "appdata"
    install_dir.mkdir()
    legacy_file = install_dir / "cloudhime_settings.json"
    legacy_file.write_text('{"language": "zh-TW"}', encoding="utf-8")
    paths = create_settings_paths(str(install_dir), str(appdata_dir))

    payload, loaded_from = load_settings_data(paths)

    assert payload == {"language": "zh-TW"}
    assert loaded_from == str(legacy_file)


def test_save_settings_does_not_fallback_to_install_directory(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    appdata_dir = tmp_path / "appdata"
    install_dir.mkdir()
    paths = create_settings_paths(str(install_dir), str(appdata_dir))

    monkeypatch.setattr(settings_store.os, "makedirs", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("blocked")))

    with pytest.raises(PermissionError, match="blocked"):
        save_settings_data(paths, {"language": "en"})

    assert not (install_dir / "cloudhime_settings.json").exists()
