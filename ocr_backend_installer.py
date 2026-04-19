from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Tuple

from ocr_backend_catalog import backend_spec, normalize_backend_name


@dataclass(frozen=True)
class BackendRuntimeState:
    installed: bool
    available: bool
    detail: str


def _has_module(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _run_command(command: list[str]) -> tuple[bool, str]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            creationflags=creationflags,
        )
    except Exception as exc:
        return False, str(exc)
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    return completed.returncode == 0, output


def install_tesseract_runtime() -> tuple[bool, str]:
    winget = shutil.which("winget")
    if winget:
        command = [
            winget,
            "install",
            "--id",
            "UB-Mannheim.TesseractOCR",
            "-e",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        ok, output = _run_command(command)
        if ok:
            return True, output or "Tesseract runtime install completed."
    return False, "Tesseract runtime is missing. Please install tesseract.exe separately."


def detect_backend_state(name: str) -> BackendRuntimeState:
    backend_name = normalize_backend_name(name)
    if backend_name == "windows":
        return BackendRuntimeState(True, True, "Built into Windows.")
    if backend_name == "tesseract":
        python_ready = _has_module("pytesseract")
        binary_ready = shutil.which("tesseract") is not None
        detail = "Ready" if python_ready and binary_ready else "Needs tesseract.exe"
        return BackendRuntimeState(python_ready and binary_ready, python_ready and binary_ready, detail)
    if backend_name == "easyocr":
        try:
            from ocr_backends import EasyOCRBackend

            backend = EasyOCRBackend()
            available = backend.available()
            if available:
                detail = "Ready (GPU)" if backend._can_use_gpu() else "Ready (CPU)"
                return BackendRuntimeState(available, available, detail)
        except Exception:
            available = False
        detail = "Ready" if available else "Needs easyocr / torch / torchvision"
        return BackendRuntimeState(available, available, detail)
    if backend_name == "rapidocr":
        python_ready = _has_module("rapidocr_onnxruntime") or _has_module("rapidocr")
        detail = "Ready" if python_ready else "Needs rapidocr-onnxruntime"
        return BackendRuntimeState(python_ready, python_ready, detail)
    spec = backend_spec(backend_name)
    if spec is None:
        return BackendRuntimeState(False, False, "Unknown backend")
    return BackendRuntimeState(False, False, "Unsupported")


def install_backend_packages(name: str) -> Tuple[bool, str]:
    backend_name = normalize_backend_name(name)
    spec = backend_spec(backend_name)
    if spec is None:
        return False, "Unknown OCR backend."
    if backend_name == "windows":
        return True, "Windows OCR does not need installation."

    messages: list[str] = []
    if spec.pip_packages:
        ok, output = _run_command([sys.executable, "-m", "pip", "install", *spec.pip_packages])
        if not ok:
            return False, output or f"{spec.label} install failed."
        if output:
            messages.append(output)

    if backend_name == "tesseract":
        state = detect_backend_state(backend_name)
        if not state.available:
            runtime_ok, runtime_output = install_tesseract_runtime()
            if not runtime_ok:
                return False, runtime_output
            if runtime_output:
                messages.append(runtime_output)
            state = detect_backend_state(backend_name)
            if not state.available:
                note = spec.install_note or "Requires tesseract.exe."
                return False, note

    return True, "\n".join(messages).strip() or f"{spec.label} install completed."
