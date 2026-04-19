from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class OCRBackendSpec:
    name: str
    label: str
    pip_packages: tuple[str, ...]
    install_note: str = ""
    requires_external_binary: bool = False


BACKEND_ORDER: tuple[str, ...] = ("windows", "tesseract", "easyocr", "rapidocr")

BACKEND_SPECS: dict[str, OCRBackendSpec] = {
    "windows": OCRBackendSpec(
        name="windows",
        label="Windows OCR",
        pip_packages=(),
        install_note="Built into Windows.",
    ),
    "tesseract": OCRBackendSpec(
        name="tesseract",
        label="Tesseract",
        pip_packages=("pytesseract",),
        install_note="Requires the Tesseract executable.",
        requires_external_binary=True,
    ),
    "easyocr": OCRBackendSpec(
        name="easyocr",
        label="EasyOCR",
        pip_packages=("easyocr", "torch", "torchvision"),
        install_note="Downloads PyTorch dependencies.",
    ),
    "rapidocr": OCRBackendSpec(
        name="rapidocr",
        label="RapidOCR",
        pip_packages=("rapidocr-onnxruntime",),
        install_note="Downloads ONNX Runtime dependencies.",
    ),
}

OPTIONAL_BACKEND_ORDER: tuple[str, ...] = tuple(name for name in BACKEND_ORDER if name != "windows")


def normalize_backend_name(name: str) -> str:
    return str(name or "").strip().lower()


def backend_spec(name: str) -> OCRBackendSpec | None:
    return BACKEND_SPECS.get(normalize_backend_name(name))


def backend_label(name: str) -> str:
    spec = backend_spec(name)
    return spec.label if spec is not None else normalize_backend_name(name) or "OCR"


def enabled_backend_chain(enabled_backends: Sequence[str] | None) -> list[str]:
    enabled = {normalize_backend_name(name) for name in (enabled_backends or [])}
    chain = ["windows"]
    for name in OPTIONAL_BACKEND_ORDER:
        if name in enabled:
            chain.append(name)
    return chain


def summarize_backend_chain(chain: Sequence[str] | None) -> str:
    names = [backend_label(name) for name in (chain or []) if normalize_backend_name(name)]
    return "Windows OCR" if not names else " + ".join(names)


def optional_backend_names() -> List[str]:
    return list(OPTIONAL_BACKEND_ORDER)
