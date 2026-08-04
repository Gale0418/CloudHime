# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path, PurePath

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


runtime_source_dir = (Path(SPECPATH) / "build" / "runtime").resolve()


def _is_duplicate_runtime_binary(entry):
    destination, source, *_ = entry
    source_path = Path(source).resolve()
    destination_path = PurePath(destination)
    return (
        source_path.is_relative_to(runtime_source_dir)
        and bool(destination_path.parts)
        and destination_path.parts[0].casefold() != "runtime"
    )

ddgs_engine_hiddenimports = collect_submodules("ddgs.engines")
fake_useragent_datas = collect_data_files("fake_useragent")
certifi_datas = collect_data_files("certifi")


a = Analysis(
    ['CloudHime.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('dictionary.json', '.'), ('LICENSE', '.'), ('THIRD_PARTY_NOTICES.md', '.'), ('build\\runtime', 'runtime'), *fake_useragent_datas, *certifi_datas],
    hiddenimports=['winrt.windows.media.ocr', 'winrt.windows.globalization', 'winrt.windows.graphics.imaging', 'winrt.windows.storage.streams', 'ddgs', 'ddgs.ddgs', 'lxml.html', 'lxml.etree', *ddgs_engine_hiddenimports],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['llama_cpp', '_llama_cpp', 'PyQt5', 'PyQt6', 'PySide2', 'easyocr', 'rapidocr', 'rapidocr_onnxruntime', 'pytesseract', 'torch', 'torchvision', 'pandas', 'scipy', 'matplotlib', 'IPython', 'tensorflow', 'keras', 'h5py', 'tensorboard', 'jax', 'jaxlib', 'jupyter', 'jupyter_core', 'jupyter_client', 'ipykernel', 'pydantic', 'pydantic_core'],
    noarchive=False,
    optimize=0,
)
a.binaries = [
    entry for entry in a.binaries
    if not _is_duplicate_runtime_binary(entry)
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CloudHime',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    manifest='packaging\\CloudHime.exe.manifest',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CloudHime',
)
