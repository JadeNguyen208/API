@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" configure_keys.py
) else (
  python configure_keys.py
)
if errorlevel 1 (
  echo.
  echo Khong the luu API key. Kiem tra Python va thu lai.
)
pause
