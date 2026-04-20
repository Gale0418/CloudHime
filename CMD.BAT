@echo off
setlocal
cd /d %~dp0
title CloudHime Source Launcher

set "APP_PY=CloudHime.py"

if not exist "%APP_PY%" (
    echo [CloudHime] Cannot find %APP_PY%
    pause
    exit /b 1
)

echo [CloudHime] Launching current source...
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python -u "%APP_PY%"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        py -3 -u "%APP_PY%"
    ) else (
        echo [CloudHime] Python launcher not found.
        pause
        exit /b 1
    )
)

set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo [CloudHime] App exited with error code %ERR%.
    pause
)
exit /b %ERR%
