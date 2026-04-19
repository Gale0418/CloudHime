@echo off
setlocal
cd /d %~dp0

python -m PyInstaller --noconfirm --clean --onefile --windowed --name CloudHime ^
  --exclude-module PyQt5 ^
  --exclude-module PyQt6 ^
  --exclude-module PySide2 ^
  --hidden-import winrt.windows.media.ocr ^
  --hidden-import winrt.windows.globalization ^
  --hidden-import winrt.windows.graphics.imaging ^
  --hidden-import winrt.windows.storage.streams ^
  --exclude-module easyocr ^
  --exclude-module rapidocr ^
  --exclude-module rapidocr_onnxruntime ^
  --exclude-module pytesseract ^
  --exclude-module torch ^
  --exclude-module torchvision ^
  CloudHime.py

endlocal
