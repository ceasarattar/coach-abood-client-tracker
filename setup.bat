@echo off
REM Coach Abood Client Tracker - one-time setup (Windows).
REM Run once after cloning:  double-click setup.bat (or run it in a terminal).
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ================================================================
echo   Coach Abood Client Tracker - Setup
echo ================================================================

REM 1. Python 3.10+ check ----------------------------------------------------
set "PY="
for %%C in (python py python3) do (
  if not defined PY (
    %%C -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "PY=%%C"
  )
)
if not defined PY (
  echo ERROR: Python 3.10+ is required but was not found.
  echo Install it from https://www.python.org/downloads/ and re-run setup.bat
  echo IMPORTANT: tick "Add python.exe to PATH" in the installer.
  pause
  exit /b 1
)
echo [1/8] Using Python:
%PY% --version

REM 2. Virtual environment ---------------------------------------------------
if not exist "venv\" (
  echo [2/8] Creating virtual environment at venv\ ...
  %PY% -m venv venv
) else (
  echo [2/8] venv\ already exists - reusing it.
)
call venv\Scripts\activate.bat

REM 3. Dependencies ----------------------------------------------------------
echo [3/8] Installing dependencies from requirements.txt ...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
echo     Installing the Cronometer browser (Playwright Chromium, ~150 MB) ...
python -m playwright install chromium || echo     (Playwright browser install skipped - run "python -m playwright install chromium" later if you use Cronometer sync.)

REM 4. .env (interactive) ----------------------------------------------------
if exist ".env" (
  echo [4/8] .env already exists - leaving it untouched.
) else (
  echo [4/8] Configuring .env ...
  echo.
  echo   Open your MASTER spreadsheet in the browser and copy the ID from the URL:
  echo     https://docs.google.com/spreadsheets/d/^<THIS-IS-THE-ID^>/edit
  echo.
  set "MASTER_ID="
  set /p MASTER_ID="  Paste your MASTER_SHEET_ID: "
  (
    echo # Coach Abood Dashboard - local secrets ^(gitignored^). Do not commit.
    echo MASTER_SHEET_ID=!MASTER_ID!
  ) > .env
  echo   Wrote .env
)

REM 5. credentials.json reminder ---------------------------------------------
echo [5/8] Checking for credentials.json ...
if not exist "credentials.json" (
  echo   NOTE: credentials.json not found yet.
  echo   Download it from Google Cloud Console ^(OAuth Desktop app^) and place it
  echo   in this folder before first launch. See docs\SETUP_WINDOWS.md.
) else (
  echo   credentials.json found.
)

REM 6. .gitignore safety -----------------------------------------------------
echo [6/8] Ensuring secrets are gitignored ...
for %%E in (.env coach_data.db credentials.json token.json clients.yaml) do (
  findstr /x /c:"%%E" .gitignore >nul 2>&1 || echo %%E>> .gitignore
)

REM 7. Initialise DB + load the workout library ------------------------------
echo [7/8] Initialising database and loading the workout library ...
python db.py
python scripts\seed_library.py

REM 8. Desktop shortcut ------------------------------------------------------
echo [8/8] Creating a Desktop shortcut ...
powershell -NoProfile -ExecutionPolicy Bypass -File "windows\create_shortcut.ps1"

echo.
echo ================================================================
echo   Setup complete.
echo.
echo   To start the dashboard:
echo     - Double-click the "Coach Dashboard" shortcut on your Desktop, OR
echo     - Double-click windows\launch.bat
echo.
echo   The browser opens automatically at http://127.0.0.1:5000
echo   On first launch a Google sign-in tab appears (use the coach's Gmail).
echo   Re-running the shortcut just focuses the running app - never a 2nd copy.
echo ================================================================
pause
endlocal
