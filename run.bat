@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "APP_DIR=%~dp0app"
cd /d "%APP_DIR%"
if errorlevel 1 exit /b 1

set "PYTHON_EXE=%APP_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found. Run app\install.ps1 first.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo Starting CloudHime...
"%PYTHON_EXE%" "%APP_DIR%\CloudHime.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo CloudHime exited with code %EXIT_CODE%.
)
pause
endlocal & exit /b %EXIT_CODE%
