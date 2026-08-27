@echo off
setlocal
cd /d "%~dp0"
echo Creating the local XM MT5 environment...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo.
echo Setup complete. Run setup_keys.bat once, open XM MT5, then run start_xm.bat.
pause
exit /b 0

:error
echo.
echo Setup failed. Check your internet connection and Python installation.
pause
exit /b 1
