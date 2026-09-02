@echo off
REM ---------------------------------------------------------------------------
REM Build the portable CheckMod.exe (double-click friendly wrapper around the
REM PowerShell script). Requires Python 3.9+ on PATH. No admin rights needed.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "packaging\build_windows.ps1" %*
echo.
pause
