from __future__ import annotations

import ocr_backend_installer as installer


def test_packaged_runtime_does_not_run_dynamic_ocr_install(monkeypatch):
    monkeypatch.setattr(installer.sys, "frozen", True, raising=False)

    def unexpected_command(command):
        raise AssertionError(f"packaged runtime attempted external install: {command!r}")

    monkeypatch.setattr(installer, "_run_command", unexpected_command)

    success, message = installer.install_backend_packages("rapidocr")

    assert success is False
    assert "packaged" in message.lower()


def test_packaged_runtime_does_not_run_winget_for_tesseract(monkeypatch):
    monkeypatch.setattr(installer.sys, "frozen", True, raising=False)

    def unexpected_command(command):
        raise AssertionError(f"packaged runtime attempted external install: {command!r}")

    monkeypatch.setattr(installer, "_run_command", unexpected_command)

    success, message = installer.install_backend_packages("tesseract")

    assert success is False
    assert "packaged" in message.lower()
