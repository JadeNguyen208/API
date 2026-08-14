@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_xm.bat once before starting the XM bridge.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" xm_bridge.py
if errorlevel 1 pause
