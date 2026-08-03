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