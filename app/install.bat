@echo off
echo ==============================================
echo        CloudHime Automated Installer
echo ==============================================
echo.
echo Starting installation process...
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install.ps1"
echo.
pause
