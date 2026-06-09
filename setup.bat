@echo off
REM ============================================================================
REM  Coach Abood Client Tracker - LOCAL DEV setup (Windows)
REM  To host the app ONLINE for you + Abood, see DEPLOY.md instead.
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
color 0B
title Coach Abood Client Tracker - Local Setup

echo.
echo  ================================================================
echo    COACH ABOOD CLIENT TRACKER - local dev setup
echo  ================================================================
echo    Runs the app on THIS computer (for development).
echo    To host it online and share it with Abood, see DEPLOY.md.
echo  ================================================================
echo.

REM --- 1. Python 3.10+ -------------------------------------------------------
echo [1/4] Checking for Python 3.10 or newer...
set "PY="
for %%C in (python py python3) do (
  if not defined PY (
    %%C -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "PY=%%C"
  )
)
if not defined PY (
  echo   X  Python 3.10+ was not found.
  echo      Install from https://www.python.org/downloads/ and tick
  echo      "Add python.exe to PATH" on the first screen, then re-run setup.bat.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)
for /f "delims=" %%V in ('%PY% --version') do echo      OK - %%V

REM --- 2. Virtual environment ------------------------------------------------
echo [2/4] Setting up the private environment (venv)...
if not exist "venv\Scripts\activate.bat" ( %PY% -m venv venv )
call venv\Scripts\activate.bat
echo      OK

REM --- 3. Dependencies -------------------------------------------------------
echo [3/4] Installing the app's components (one-time download)...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
  echo   X  Could not install components. Check your internet connection and re-run.
  pause
  exit /b 1
)
echo      OK

REM --- 4. Database (tables + workout library) --------------------------------
echo [4/4] Preparing the local database...
python db.py
echo      OK

echo.
echo  ================================================================
echo    SETUP COMPLETE
echo  ================================================================
echo    Start the app:   python run.py        (opens http://127.0.0.1:5000)
echo.
echo    Connect Google Sheets locally (optional): drop service_account.json
echo    next to app.py and set MASTER_SHEET_ID in a .env file.
echo    To host it online for you + Abood, see DEPLOY.md.
echo  ================================================================
echo.
set "LAUNCH="
set /p LAUNCH="   Start the app now? [Y/n]: "
if /i not "!LAUNCH!"=="N" ( start "" cmd /c "call venv\Scripts\activate.bat && python run.py" )
endlocal
