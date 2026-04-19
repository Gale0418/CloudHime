# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['CloudHime.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['winrt.windows.media.ocr', 'winrt.windows.globalization', 'winrt.windows.graphics.imaging', 'winrt.windows.storage.streams'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'easyocr', 'rapidocr', 'rapidocr_onnxruntime', 'pytesseract', 'torch', 'torchvision'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CloudHime',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
