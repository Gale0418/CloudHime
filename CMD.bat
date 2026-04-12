@echo off
setlocal
cd /d "%~dp0"

set "APP_EXE=%~dp0dist\CloudHime.exe"
set "APP_PY=%~dp0CloudHime.py"
set "PYTHONW=C:\Users\USER\miniconda3\pythonw.exe"
set "PYTHON=C:\Users\USER\miniconda3\python.exe"

if exist "%APP_EXE%" (
    start "" "%APP_EXE%"
    exit /b 0
)

if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%APP_PY%"
    exit /b 0
)

if exist "%PYTHON%" (
    start "" "%PYTHON%" "%APP_PY%"
    exit /b 0
)

echo No available launcher found.
echo 1. dist\CloudHime.exe
echo 2. C:\Users\USER\miniconda3\pythonw.exe
echo 3. C:\Users\USER\miniconda3\python.exe
pause
exit /b 1
