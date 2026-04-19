@echo off
setlocal
cd /d "%~dp0"

set "APP_PY=%~dp0CloudHime.py"
set "PYTHON=C:\Users\USER\miniconda3\python.exe"
set "PYTHONW=C:\Users\USER\miniconda3\pythonw.exe"

if exist "%PYTHON%" (
    start "" "%PYTHON%" "%APP_PY%"
    exit /b 0
)

if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%APP_PY%"
    exit /b 0
)

echo No Python launcher found.
echo 1. C:\Users\USER\miniconda3\python.exe
echo 2. C:\Users\USER\miniconda3\pythonw.exe
pause
exit /b 1
