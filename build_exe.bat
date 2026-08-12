@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Windows PowerShell must not import the PowerShell 7 Utility module from the caller's environment.
set "CLOUDHIME_ORIGINAL_PS_MODULE_PATH=%PSModulePath%"
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules;%ProgramFiles%\WindowsPowerShell\Modules"

set "APP_NAME=CloudHime"
set "DIST_DIR=dist\%APP_NAME%"
set "ZIP_FILE=dist\%APP_NAME%.zip"
set "RUNTIME_STAGE=build\runtime"
set "BUILD_EXIT_CODE=0"
set "PYTHON=py -3.10-64"
%PYTHON% -c "import platform, sys; ok = sys.implementation.name == 'cpython' and sys.version_info[:2] == (3, 10) and sys.platform == 'win32' and platform.machine().lower() in ('amd64', 'x86_64'); sys.exit('Python 3.10 x64 is required for the production release build.') if not ok else None"
if errorlevel 1 (
  echo Python 3.10 x64 is required for the production release build.
  goto :failure
)

if not exist "runtime\llama-server.exe" (
  echo Missing runtime\llama-server.exe
  goto :failure
)
if not exist "assets\bg_dark.jpg" (
  echo Missing assets\bg_dark.jpg
  goto :failure
)
if not exist "assets\bg_light.jpg" (
  echo Missing assets\bg_light.jpg
  goto :failure
)
if not exist "assets\cloudhime_logo.png" (
  echo Missing assets\cloudhime_logo.png
  goto :failure
)
for %%F in (dictionary.json LICENSE THIRD_PARTY_NOTICES.md) do (
  if not exist "%%F" (
    echo Missing %%F
    goto :failure
  )
)

if exist "%RUNTIME_STAGE%" rmdir /s /q "%RUNTIME_STAGE%"
mkdir "%RUNTIME_STAGE%"
if errorlevel 1 (
  goto :failure
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
    goto :failure
  )
  copy /y "runtime\%%F" "%RUNTIME_STAGE%\" >nul
  if errorlevel 1 (
    goto :failure
  )
)

for %%F in (runtime\ggml-cpu-*.dll) do (
  copy /y "%%~fF" "%RUNTIME_STAGE%\" >nul
  if errorlevel 1 (
    goto :failure
  )
)

for /f "delims=" %%C in ('git rev-parse HEAD 2^>nul') do set "RUNTIME_COMMIT=%%C"
if not defined RUNTIME_COMMIT (
  echo Unable to determine the runtime source commit.
  goto :failure
)
%PYTHON% packaging\runtime_manifest.py --runtime-dir "%RUNTIME_STAGE%" --output "%RUNTIME_STAGE%\runtime-manifest.json" --source-commit "%RUNTIME_COMMIT%" --backend "cuda" --architecture "x64" --version-timeout 120
if errorlevel 1 (
  echo Runtime manifest generation failed. The staged llama-server must pass --version.
  goto :failure
)
rem CloudHime ships a lightweight Windows OCR build.
rem Optional OCR backends are source-mode only; packaged builds do not install Python packages.
%PYTHON% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is not installed. Run "py -3.10-64 -m pip install pyinstaller -r requirements-lock-win-amd64-py310.txt" first.
  goto :failure
)

%PYTHON% -c "import ddgs, lxml, primp, fake_useragent, certifi" >nul 2>&1
if errorlevel 1 (
  echo Missing DDGS runtime dependencies. Install requirements.txt before building the packaged release.
  goto :failure
)

if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%ZIP_FILE%" del /f /q "%ZIP_FILE%"

rem Keep the release independent from optional TensorFlow/Keras OCR environments.
pwsh -NoLogo -NoProfile -File "packaging\prepare_release_provenance.ps1"
if errorlevel 1 (
  echo Release provenance preparation failed.
  goto :failure
)
echo Building %APP_NAME% release...
%PYTHON% -m PyInstaller --noconfirm --clean CloudHime.spec
if errorlevel 1 (
  goto :failure
)

set "CLOUDHIME_PACKAGED_IMPORT_SMOKE=1"
"%DIST_DIR%\CloudHime.exe" >nul 2>&1
if errorlevel 1 (
  echo Frozen DDGS import smoke failed.
  goto :failure
)
set "CLOUDHIME_PACKAGED_IMPORT_SMOKE="
powershell -NoProfile -ExecutionPolicy Bypass -File "packaging\verify_release_dist.ps1" -DistDir "%DIST_DIR%"
if errorlevel 1 (
  echo Release preflight failed.
  goto :failure
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\%APP_NAME%\*' -DestinationPath 'dist\%APP_NAME%.zip' -Force"
if errorlevel 1 (
  goto :failure
)

goto :cleanup

:failure
set "BUILD_EXIT_CODE=1"
goto :cleanup

:cleanup
if exist "%RUNTIME_STAGE%" rmdir /s /q "%RUNTIME_STAGE%"
if defined CLOUDHIME_ORIGINAL_PS_MODULE_PATH (
  set "PSModulePath=%CLOUDHIME_ORIGINAL_PS_MODULE_PATH%"
) else (
  set "PSModulePath="
)
if exist "%RUNTIME_STAGE%" set "BUILD_EXIT_CODE=1"

if not "%BUILD_EXIT_CODE%"=="0" (
  echo Build failed.
  endlocal
  exit /b 1
)

echo Done: %ZIP_FILE%
endlocal
exit /b 0
