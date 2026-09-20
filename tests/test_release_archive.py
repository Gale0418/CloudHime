import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

spec = importlib.util.spec_from_file_location(
    "release_archive", Path(__file__).resolve().parents[1] / "packaging/release_archive.py"
)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "_internal").mkdir(parents=True)
    (dist / "CloudHime.exe").write_bytes(b"test exe")
    source = tmp_path / "source"
    source.mkdir()
    manifest = []
    for name in ("model.gguf", "mmproj.gguf"):
        data = name.encode()
        (source / name).write_bytes(data)
        manifest.append(SimpleNamespace(name=name, size=len(data), sha256=hashlib.sha256(data).hexdigest()))
    monkeypatch.setattr(archive, "GEMMA_ASSET_MANIFEST", manifest)
    return dist, source


def test_stage_and_verify_full_bundle(bundle):
    dist, source = bundle
    archive.stage_models(dist, source)
    assert archive.verify_models(dist, "full") == 2
    with pytest.raises(ValueError, match="Light release"):
        archive.verify_models(dist, "light")
    with pytest.raises(FileExistsError):
        archive.stage_models(dist, source)


def test_corrupt_source_is_rejected_before_copy(bundle):
    dist, source = bundle
    (source / "model.gguf").write_bytes(b"x" * len(b"model.gguf"))
    with pytest.raises(ValueError, match="SHA256"):
        archive.stage_models(dist, source)
    assert not (dist / "_internal/models").exists()


def test_missing_terms_and_extra_model_fail_closed(bundle):
    dist, source = bundle
    archive.stage_models(dist, source)
    (dist / "rogue.gguf").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="exactly"):
        archive.verify_models(dist)
    (dist / "rogue.gguf").unlink()
    (dist / "_internal/models/NOTICE.txt").unlink()
    with pytest.raises(ValueError, match="terms"):
        archive.verify_models(dist)


def test_zip64_preserves_files_and_does_not_overwrite(bundle, tmp_path, monkeypatch):
    dist, source = bundle
    archive.stage_models(dist, source)
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 4)
    output = tmp_path / "release.zip"
    archive.create_archive(dist, output)
    with zipfile.ZipFile(output) as result:
        assert result.testzip() is None
        assert result.read("_internal/models/model.gguf") == b"model.gguf"
    with pytest.raises(FileExistsError):
        archive.create_archive(dist, output)
    with pytest.raises(ValueError, match="outside"):
        archive.create_archive(dist, dist / "self.zip")


def test_full_requires_models_but_light_does_not(bundle):
    dist, _ = bundle
    assert archive.verify_models(dist, "light") == 0
    with pytest.raises(ValueError, match="exactly"):
        archive.verify_models(dist, "full")


def test_msix_upload_supports_zip64_without_changing_payload(tmp_path, monkeypatch):
    source = tmp_path / "CloudHime.msix"
    source.write_bytes(b"test MSIX payload")
    output = tmp_path / "upload.zip"
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 4)
    archive.create_upload_archive(source, output)
    with zipfile.ZipFile(output) as result:
        assert result.namelist() == [source.name]
        assert result.read(source.name) == source.read_bytes()
    with pytest.raises(FileExistsError):
        archive.create_upload_archive(source, output)


def test_msix_upload_builder_uses_large_file_writer():
    script = (Path(__file__).resolve().parents[1] / "packaging/build_msix.ps1").read_text(encoding="utf-8")
    assert '"release_archive.py") zip-upload --source $package --output $uploadZip' in script
    assert "Compress-Archive" not in script
