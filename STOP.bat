@echo off
REM ColdChain Rescue — stop backend and frontend.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\coldchain.ps1" stop
echo.
pause >nul