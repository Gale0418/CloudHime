import base64
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("installed_guard", Path(__file__).parents[1] / "packaging/verify_installed_dependencies.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def _record_hash(data):
    value = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
    return f"sha256={value}", str(len(data))


def _add_wheel_file(wheel, wheel_relative, trusted_data, installed_path, installed_relative, installed_data=None):
    report, wheel_dir, dist, _ = wheel
    wheel_path = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    info_root = "sample-1.0.dist-info"
    rows = list(csv.reader(entries[info_root + "/RECORD"].decode().splitlines()))
    digest, size = _record_hash(trusted_data)
    rows.append([wheel_relative, digest, size])
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    entries[info_root + "/RECORD"] = buf.getvalue().encode()
    entries[wheel_relative] = trusted_data
    with zipfile.ZipFile(wheel_path, "w") as target:
        for name, data in entries.items():
            target.writestr(name, data)
    installed_path.parent.mkdir(parents=True, exist_ok=True)
    installed_path.write_bytes(trusted_data if installed_data is None else installed_data)
    record = dist._path / "RECORD"
    installed_rows = list(csv.reader(record.read_text(encoding="utf-8").splitlines()))
    installed_hash, installed_size = _record_hash(installed_path.read_bytes())
    installed_rows.append([installed_relative, installed_hash, installed_size])
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(installed_rows)
    record.write_text(buf.getvalue(), encoding="utf-8")
    data = json.loads(report.read_text(encoding="utf-8"))
    data["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    report.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def wheel(tmp_path):
    name, version = "sample", "1.0"
    filename = "sample-1.0-py3-none-any.whl"
    info_root = "sample-1.0.dist-info"
    files = {
        "sample/native.pyd": b"pinned native bytes",
        f"{info_root}/METADATA": b"Metadata-Version: 2.1\nName: sample\nVersion: 1.0\n\n",
        f"{info_root}/WHEEL": b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: false\nTag: py3-none-any\n",
    }
    record = []
    for relative, data in files.items():
        digest, size = _record_hash(data)
        record.append((relative, digest, size))
    record.append((f"{info_root}/RECORD", "", ""))
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(record)
    files[f"{info_root}/RECORD"] = buf.getvalue().encode()
    wheel_path = tmp_path / "wheels" / filename
    wheel_path.parent.mkdir()
    with zipfile.ZipFile(wheel_path, "w") as archive:
        for relative, data in files.items():
            archive.writestr(relative, data)

    install_root = tmp_path / "site-packages"
    for relative, data in files.items():
        target = install_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    dist = importlib.metadata.PathDistribution(install_root / info_root)
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"install": [{
        "metadata": {"name": name, "version": version},
        "download_info": {
            "url": f"https://files.example/{filename}",
            "archive_info": {"hashes": {"sha256": hashlib.sha256(wheel_path.read_bytes()).hexdigest()}},
        },
    }]}), encoding="utf-8")
    return report, wheel_path.parent, dist, install_root / "sample/native.pyd"


def test_original_wheel_passes(wheel):
    report, wheel_dir, dist, _ = wheel
    assert guard.verify(report, wheel_dir, distributions=[dist]) == {"packages": 1, "hashedFiles": 3}


def test_overwritten_native_file_fails_against_trusted_wheel(wheel):
    report, wheel_dir, dist, payload = wheel
    payload.write_bytes(b"another wheel overwrote this")
    with pytest.raises(ValueError, match="hash mismatch"):
        guard.verify(report, wheel_dir, distributions=[dist])


def test_missing_native_file_fails(wheel):
    report, wheel_dir, dist, payload = wheel
    payload.unlink()
    with pytest.raises(ValueError, match="Missing/unreadable"):
        guard.verify(report, wheel_dir, distributions=[dist])


def test_unhashed_trusted_payload_fails(wheel):
    report, wheel_dir, dist, _ = wheel
    wheel_path = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    record_path = "sample-1.0.dist-info/RECORD"
    rows = list(csv.reader(entries[record_path].decode().splitlines()))
    rows[0][1:] = ["", ""]
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    entries[record_path] = buf.getvalue().encode()
    with zipfile.ZipFile(wheel_path, "w") as target:
        for name, data in entries.items():
            target.writestr(name, data)
    # Update the report's archive digest: the changed archive is still the declared artifact.
    data = json.loads(report.read_text(encoding="utf-8"))
    data["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    report.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unhashed trusted wheel payload"):
        guard.verify(report, wheel_dir, distributions=[dist])


def test_installed_record_cannot_be_modified_to_hide_overwrite(wheel):
    report, wheel_dir, dist, payload = wheel
    payload.write_bytes(b"overwritten")
    record = dist._path / "RECORD"
    rows = list(csv.reader(record.read_text(encoding="utf-8").splitlines()))
    rows[0][1], rows[0][2] = _record_hash(payload.read_bytes())
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    record.write_text(buf.getvalue(), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        guard.verify(report, wheel_dir, distributions=[dist])


def test_missing_wheel_or_report_hash_fails(wheel):
    report, wheel_dir, dist, _ = wheel
    (wheel_dir / "sample-1.0-py3-none-any.whl").unlink()
    with pytest.raises(ValueError, match="Missing trusted wheel"):
        guard.verify(report, wheel_dir, distributions=[dist])


def test_missing_report_hash_fails(wheel):
    report, wheel_dir, dist, _ = wheel
    data = json.loads(report.read_text(encoding="utf-8"))
    del data["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"]
    report.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing trusted wheel URL/hash"):
        guard.verify(report, wheel_dir, distributions=[dist])


def test_ambiguous_distribution_fails(wheel):
    report, wheel_dir, dist, _ = wheel
    with pytest.raises(ValueError, match="does not match"):
        guard.verify(report, wheel_dir, distributions=[dist, dist])


def test_two_reported_opencv_variants_fail(wheel):
    report, wheel_dir, dist, _ = wheel
    data = json.loads(report.read_text(encoding="utf-8"))
    second = dict(data["install"][0])
    second["metadata"] = {"name": "opencv-python-headless", "version": "4.13"}
    data["install"][0]["metadata"] = {"name": "opencv-python", "version": "4.13"}
    data["install"].append(second)
    report.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Multiple OpenCV variants"):
        guard.verify(report, wheel_dir, distributions=[dist])


def test_second_installed_opencv_variant_fails(wheel, tmp_path):
    report, wheel_dir, dist, _ = wheel
    data = json.loads(report.read_text(encoding="utf-8"))
    data["install"][0]["metadata"] = {"name": "opencv-python-headless", "version": "4.13"}
    report.write_text(json.dumps(data), encoding="utf-8")
    info = tmp_path / "extra.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Name: opencv-python\nVersion: 5.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Conflicting OpenCV"):
        guard.verify(report, wheel_dir, distributions=[dist, importlib.metadata.PathDistribution(info)])


def test_bytecode_cache_is_the_only_unhashed_record_exception(wheel):
    report, wheel_dir, dist, _ = wheel
    record = dist._path / "RECORD"
    record.write_text(record.read_text(encoding="utf-8") + "sample/__pycache__/module.cpython-310.pyc,,\n", encoding="utf-8")
    assert guard.verify(report, wheel_dir, distributions=[dist])["hashedFiles"] == 3


def test_data_purelib_record_uses_relocated_install_path(wheel):
    report, wheel_dir, dist, _ = wheel
    data = b"VALUE = 42\n"
    installed = dist.locate_file("sample/relocated.py")
    _add_wheel_file(wheel, "sample-1.0.data/purelib/sample/relocated.py", data,
                    Path(installed), "sample/relocated.py")
    assert guard.verify(report, wheel_dir, distributions=[dist])["hashedFiles"] == 4


def test_data_script_shebang_rewrite_preserves_trusted_payload(wheel, tmp_path, monkeypatch):
    report, wheel_dir, dist, _ = wheel
    scripts = tmp_path / "scripts"
    get_path = guard.sysconfig.get_path
    monkeypatch.setattr(guard.sysconfig, "get_path", lambda scheme: str(scripts) if scheme == "scripts" else get_path(scheme))
    trusted = b"#!python\nprint('trusted')\n"
    installed = scripts / "runner.py"
    installed_data = f"#!{sys.executable}\nprint('trusted')\n".encode()
    record_key = Path(os.path.relpath(installed, dist.locate_file(""))).as_posix()
    _add_wheel_file(wheel, "sample-1.0.data/scripts/runner.py", trusted, installed, record_key, installed_data)
    assert guard.verify(report, wheel_dir, distributions=[dist])["hashedFiles"] == 4

    installed.write_bytes(installed_data + b"# altered\n")
    record = dist._path / "RECORD"
    rows = list(csv.reader(record.read_text(encoding="utf-8").splitlines()))
    for row in rows:
        if row[0] == record_key:
            row[1], row[2] = _record_hash(installed.read_bytes())
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    record.write_text(buf.getvalue(), encoding="utf-8")
    with pytest.raises(ValueError, match="Rewritten script payload mismatch"):
        guard.verify(report, wheel_dir, distributions=[dist])
