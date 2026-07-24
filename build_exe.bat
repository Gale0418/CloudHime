@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=CloudHime"
set "DIST_DIR=dist\%APP_NAME%"
set "ZIP_FILE=dist\%APP_NAME%.zip"
set "RUNTIME_STAGE=build\runtime"
set "BUILD_EXIT_CODE=0"

if not exist "runtime\llama-server.exe" (
  echo Missing runtime\llama-server.exe
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
)
if not exist "assets\bg_dark.jpg" (
  echo Missing assets\bg_dark.jpg
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
)
if not exist "assets\bg_light.jpg" (
  echo Missing assets\bg_light.jpg
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
)
if not exist "dictionary.json" (
  echo Missing dictionary.json
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
)

if exist "%RUNTIME_STAGE%" rmdir /s /q "%RUNTIME_STAGE%"
mkdir "%RUNTIME_STAGE%"
if errorlevel 1 (
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
)

for %%F in (
  llama-server.exe
  llama-server-impl.dll
  llama-common.dll
  llama.dll
  ggml.dll
  ggml-base.dll
  ggml-cpu-x64.dll
  ggml-cuda.dll
  mtmd.dll
  libomp140.x86_64.dll
  cublas64_12.dll
  cublasLt64_12.dll
  cudart64_12.dll
) do (
  if not exist "runtime\%%F" (
    echo Missing runtime\%%F
    set "BUILD_EXIT_CODE=1"
    goto :cleanup
  )
  copy /y "runtime\%%F" "%RUNTIME_STAGE%\" >nul
  if errorlevel 1 (
    set "BUILD_EXIT_CODE=1"
    goto :cleanup
  )
)

for %%F in (runtime\ggml-cpu-*.dll) do (
  copy /y "%%~fF" "%RUNTIME_STAGE%\" >nul
  if errorlevel 1 (
    set "BUILD_EXIT_CODE=1"
    goto :cleanup
  )
)

rem CloudHime ships a lightweight Windows OCR build.
rem Optional OCR backends are installed on demand from the app, so they stay out of the release bundle.
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is not installed. Run "python -m pip install pyinstaller -r requirements.txt" first.
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
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
  --add-data "assets;assets" ^
  --add-data "dictionary.json;." ^
  --add-data "%RUNTIME_STAGE%;runtime" ^
  CloudHime.py
if errorlevel 1 (
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\%APP_NAME%\*' -DestinationPath 'dist\%APP_NAME%.zip' -Force"
if errorlevel 1 (
  set "BUILD_EXIT_CODE=1"
  goto :cleanup
)

:cleanup
if exist "%RUNTIME_STAGE%" rmdir /s /q "%RUNTIME_STAGE%"
if exist "%RUNTIME_STAGE%" set "BUILD_EXIT_CODE=1"

if not "%BUILD_EXIT_CODE%"=="0" (
  echo Build failed.
  endlocal
  exit /b 1
)

echo Done: %ZIP_FILE%
endlocal
exit /b 0
