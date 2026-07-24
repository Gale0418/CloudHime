@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found. Run install.ps1 first.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo Starting CloudHime with %PYTHON_EXE%...
"%PYTHON_EXE%" "%~dp0CloudHime.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo CloudHime exited with code %EXIT_CODE%.
)
pause
endlocal & exit /b %EXIT_CODE%
