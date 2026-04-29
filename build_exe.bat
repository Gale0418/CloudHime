@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=CloudHime"
set "DIST_DIR=dist\%APP_NAME%"
set "ZIP_FILE=dist\%APP_NAME%.zip"

rem CloudHime ships a lightweight Windows OCR build.
rem Optional OCR backends are installed on demand from the app, so they stay out of the release bundle.
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is not installed. Run "python -m pip install pyinstaller -r requirements.txt" first.
  exit /b 1
)

if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%ZIP_FILE%" del /f /q "%ZIP_FILE%"

echo Building %APP_NAME% release...
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "%APP_NAME%" ^
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
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\%APP_NAME%\*' -DestinationPath 'dist\%APP_NAME%.zip' -Force"
if errorlevel 1 exit /b 1

echo Done: %ZIP_FILE%
endlocal
