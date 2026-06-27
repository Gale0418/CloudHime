@echo off
set CONDA_PATH=%USERPROFILE%\Miniconda3
set ENV_NAME=cloudhime_env

if not exist "%CONDA_PATH%\Scripts\activate.bat" (
    echo [ERROR] Miniconda not found! Please run install.bat first.
    pause
    exit /b
)

echo Activating environment %ENV_NAME%...
call "%CONDA_PATH%\Scripts\activate.bat" %ENV_NAME%

echo Starting CloudHime...
python "%~dp0CloudHime.py"

pause
