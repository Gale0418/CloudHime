@echo off
setlocal
cd /d %~dp0

if exist "dist\CloudHime" rmdir /s /q "dist\CloudHime"
if exist "dist\CloudHime.zip" del /f /q "dist\CloudHime.zip"
if exist "dist\CloudHime.exe" del /f /q "dist\CloudHime.exe"

python -m PyInstaller --noconfirm --clean --onedir --windowed --name CloudHime ^
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
  --exclude-module pandas ^
  --exclude-module scipy ^
  --exclude-module matplotlib ^
  --exclude-module IPython ^
  --exclude-module jupyter ^
  --exclude-module jupyter_core ^
  --exclude-module jupyter_client ^
  --exclude-module ipykernel ^
  --exclude-module pydantic ^
  --exclude-module pydantic_core ^
  --exclude-module lxml ^
  CloudHime.py

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\CloudHime\*' -DestinationPath 'dist\CloudHime.zip' -Force"

endlocal
