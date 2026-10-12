@echo off
REM ColdChain Rescue — one-click start.
REM Double-click this file. To stop, run scripts\stop.bat (or close the apps).

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\coldchain.ps1" start

echo.
echo   Press any key to close this window.
echo   (backend and frontend keep running in the background)
pause >nul