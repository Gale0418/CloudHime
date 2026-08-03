import os

import pytest

from secret_store import SecretStore, SecretStoreError


@pytest.mark.skipif(os.name != "nt", reason="CloudHime uses Windows DPAPI")
def test_secret_store_round_trip_is_encrypted(tmp_path):
    path = tmp_path / "google_api_key.dpapi"
    store = SecretStore(path)

    store.set("secret-key")

    assert path.exists()
    assert path.read_bytes() != b"secret-key"
    assert store.get() == "secret-key"

    store.delete()
    assert store.get() == ""


@pytest.mark.skipif(os.name != "nt", reason="CloudHime uses Windows DPAPI")
def test_secret_store_rejects_corrupt_ciphertext(tmp_path):
    path = tmp_path / "google_api_key.dpapi"
    path.write_bytes(b"not-dpapi-ciphertext")

    with pytest.raises(SecretStoreError):
        SecretStore(path).get()

def test_secret_store_wraps_filesystem_read_errors(monkeypatch, tmp_path):
    store = SecretStore(tmp_path / "google_api_key.dpapi")

    def fail_read(_path):
        raise PermissionError("blocked")

    monkeypatch.setattr(type(store.path), "read_bytes", fail_read)

    with pytest.raises(SecretStoreError, match="could not read secret store"):
        store.get()

def test_secret_store_tombstone_survives_secret_deletion(tmp_path):
    store = SecretStore(tmp_path / "google_api_key.dpapi")

    store.mark_legacy_sources_disabled()
    store.delete()

    assert store.legacy_sources_disabled() is True