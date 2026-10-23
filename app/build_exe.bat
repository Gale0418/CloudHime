@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Windows PowerShell must not import the PowerShell 7 Utility module from the caller's environment.
set "CLOUDHIME_ORIGINAL_PS_MODULE_PATH=%PSModulePath%"
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules;%ProgramFiles%\WindowsPowerShell\Modules"

set "APP_NAME=CloudHime"
set "DIST_DIR=dist\%APP_NAME%"
set "RUNTIME_STAGE=build\runtime"
set "BUILD_EXIT_CODE=0"
set "BUILD_PYTHON_PROBE="
set "PYTHON=py -3.10-64"
rem Optional absolute interpreter path for an isolated hash-locked build venv.
if defined CLOUDHIME_BUILD_PYTHON if not exist "%CLOUDHIME_BUILD_PYTHON%" goto :failure
if defined CLOUDHIME_BUILD_PYTHON set PYTHON="%CLOUDHIME_BUILD_PYTHON%"
rem Full offline release is the default. Set CLOUDHIME_RELEASE_FLAVOR=light to omit models.
if not defined CLOUDHIME_RELEASE_FLAVOR set "CLOUDHIME_RELEASE_FLAVOR=full"
if not "%CLOUDHIME_RELEASE_FLAVOR%"=="full" if not "%CLOUDHIME_RELEASE_FLAVOR%"=="light" goto :failure
if not defined CLOUDHIME_MODEL_SOURCE set "CLOUDHIME_MODEL_SOURCE=%LOCALAPPDATA%\CloudHime\models\gemma-3-4b-it\ggml-org-ab31416a"
set "BUILD_REQUIREMENTS=requirements-build-win-amd64-py310.txt"
%PYTHON% -c "import platform, sys; ok = sys.implementation.name == 'cpython' and sys.version_info[:2] == (3, 10) and sys.platform == 'win32' and platform.machine().lower() in ('amd64', 'x86_64'); sys.exit('Python 3.10 x64 is required for the production release build.') if not ok else None"
if errorlevel 1 (
  echo Python 3.10 x64 is required for the production release build.
  goto :failure
)
set "BUILD_PYTHON_PATH="
set "BUILD_PYTHON_PROBE=%TEMP%\CloudHime-python-%RANDOM%-%RANDOM%.txt"
if exist "%BUILD_PYTHON_PROBE%" (
  set "BUILD_PYTHON_PROBE="
  goto :failure
)
%PYTHON% -c "import sys; print(sys.executable)" > "%BUILD_PYTHON_PROBE%"
if errorlevel 1 goto :failure
for /f "usebackq delims=" %%I in ("%BUILD_PYTHON_PROBE%") do set "BUILD_PYTHON_PATH=%%I"
del /q "%BUILD_PYTHON_PROBE%"
if exist "%BUILD_PYTHON_PROBE%" goto :failure
set "BUILD_PYTHON_PROBE="
if not defined BUILD_PYTHON_PATH goto :failure

if not exist "%BUILD_REQUIREMENTS%" (
  echo Missing %BUILD_REQUIREMENTS%. Install the pinned release build tooling first.
  goto :failure
)
if not exist "runtime\llama-server.exe" (
  echo Missing runtime\llama-server.exe
  goto :failure
)
if not exist "assets\bg_dark.png" (
  echo Missing assets\bg_dark.png
  goto :failure
)
if not exist "assets\bg_light.png" (
  echo Missing assets\bg_light.png
  goto :failure
)
if not exist "assets\cloudhime_logo.png" (
  echo Missing assets\cloudhime_logo.png
  goto :failure
)
for %%F in (dictionary.json LICENSE NOTICE AUTHORS.md BRANDING.md THIRD_PARTY_NOTICES.md) do (
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

if exist "runtime\runtime-source.json" (
  copy /y "runtime\runtime-source.json" "%RUNTIME_STAGE%\" >nul
  if errorlevel 1 (
    goto :failure
  )
)

if not defined LLAMA_RUNTIME_COMMIT if exist "runtime\llama-runtime-commit.txt" set /p LLAMA_RUNTIME_COMMIT=<"runtime\llama-runtime-commit.txt"
if not defined LLAMA_RUNTIME_COMMIT (
  echo Missing explicit llama runtime commit provenance.
  echo Set LLAMA_RUNTIME_COMMIT or provide runtime\llama-runtime-commit.txt.
  goto :failure
)
set "RUNTIME_COMMIT=%LLAMA_RUNTIME_COMMIT%"
%PYTHON% packaging\runtime_manifest.py --runtime-dir "%RUNTIME_STAGE%" --output "%RUNTIME_STAGE%\runtime-manifest.json" --source-commit "%RUNTIME_COMMIT%" --backend "cuda" --architecture "x64" --version-timeout 120
if errorlevel 1 (
  echo Runtime manifest generation failed. The staged llama-server must pass --version.
  goto :failure
)
rem CloudHime ships a lightweight Windows OCR build.
rem Optional OCR backends are source-mode only; packaged builds do not install Python packages.
%PYTHON% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is not installed. Run "py -3.10-64 -m pip install --require-hashes -r %BUILD_REQUIREMENTS%" first.
  goto :failure
)

%PYTHON% -c "import ddgs, lxml, primp, fake_useragent, certifi" >nul 2>&1
if errorlevel 1 (
  echo Missing DDGS runtime dependencies. Install requirements.txt before building the packaged release.
  goto :failure
)

rem Keep the release independent from optional TensorFlow/Keras OCR environments.
pwsh -NoLogo -NoProfile -File "packaging\prepare_release_provenance.ps1"
if errorlevel 1 (
  echo Release provenance preparation failed.
  goto :failure
)
echo Building %APP_NAME% release...
%PYTHON% -m pip download --require-hashes --no-deps --dest "build\production-wheels" -r requirements-lock-win-amd64-py310.txt
if errorlevel 1 goto :failure
%PYTHON% packaging\verify_installed_dependencies.py --report "build\provenance\production-pip-report.json" --wheel-dir "build\production-wheels"
if errorlevel 1 goto :failure

if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
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
powershell -NoProfile -ExecutionPolicy Bypass -File "packaging\verify_release_dist.ps1" -DistDir "%DIST_DIR%" -PythonPath "%BUILD_PYTHON_PATH%" -ModelBundle light
if errorlevel 1 (
  echo Release preflight failed.
  goto :failure
)

if "%CLOUDHIME_RELEASE_FLAVOR%"=="full" (
  %PYTHON% packaging\release_archive.py stage --dist "%DIST_DIR%" --source "%CLOUDHIME_MODEL_SOURCE%"
  if errorlevel 1 goto :failure
  powershell -NoProfile -ExecutionPolicy Bypass -File "packaging\verify_release_dist.ps1" -DistDir "%DIST_DIR%" -PythonPath "%BUILD_PYTHON_PATH%" -ModelBundle full
  if errorlevel 1 goto :failure
)
goto :cleanup

:failure
set "BUILD_EXIT_CODE=1"
goto :cleanup

:cleanup
if defined BUILD_PYTHON_PROBE if exist "%BUILD_PYTHON_PROBE%" del /q "%BUILD_PYTHON_PROBE%"
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

echo Done: %DIST_DIR%
endlocal
exit /b 0
