# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

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
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'easyocr', 'rapidocr', 'rapidocr_onnxruntime', 'pytesseract', 'torch', 'torchvision', 'pandas', 'scipy', 'matplotlib', 'IPython', 'tensorflow', 'keras', 'h5py', 'tensorboard', 'jax', 'jaxlib', 'jupyter', 'jupyter_core', 'jupyter_client', 'ipykernel', 'pydantic', 'pydantic_core'],
    noarchive=False,
    optimize=0,
)
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
