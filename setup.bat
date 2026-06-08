@echo off
REM ============================================================================
REM  Coach Abood Client Tracker - one-time setup (Windows)
REM  Just double-click this file. It installs everything, asks you to paste a
REM  couple of values, and makes a Desktop shortcut. Safe to run again anytime.
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
color 0B
title Coach Abood Client Tracker - Setup

echo.
echo  ================================================================
echo    COACH ABOOD CLIENT TRACKER - SETUP
echo  ================================================================
echo    This takes about 5 minutes and you only do it once.
echo    Have these two things ready (Ceasar gives them to you):
echo      1) the file  credentials.json
echo      2) your MASTER spreadsheet link
echo  ================================================================
echo.
pause

REM --- 1. Python 3.10+ -------------------------------------------------------
echo.
echo [1/7] Checking for Python 3.10 or newer...
set "PY="
for %%C in (python py python3) do (
  if not defined PY (
    %%C -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "PY=%%C"
  )
)
if not defined PY (
  echo.
  echo   X  Python 3.10+ was not found.
  echo      1. Go to  https://www.python.org/downloads/
  echo      2. Download and run the installer.
  echo      3. IMPORTANT: tick "Add python.exe to PATH" on the first screen.
  echo      4. Then double-click setup.bat again.
  echo.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)
for /f "delims=" %%V in ('%PY% --version') do echo      OK - %%V

REM --- 2. Virtual environment ------------------------------------------------
echo.
echo [2/7] Setting up the private environment (venv)...
if not exist "venv\Scripts\activate.bat" (
  %PY% -m venv venv
)
call venv\Scripts\activate.bat
echo      OK

REM --- 3. Dependencies -------------------------------------------------------
echo.
echo [3/7] Installing the app's components (one-time download)...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
  echo   X  Could not install components. Check your internet connection and re-run.
  pause
  exit /b 1
)
echo      OK

REM --- 4. credentials.json gate ---------------------------------------------
echo.
echo [4/7] Checking for the Google connection file (credentials.json)...
:CHECK_CREDS
if exist "credentials.json" (
  echo      OK - credentials.json found.
) else (
  echo.
  echo   !  credentials.json is NOT in this folder yet.
  echo      - Get the file "credentials.json" from Ceasar.
  echo      - Copy it INTO this folder:
  echo          %cd%
  echo.
  echo      [Enter] = I've put it here, check again      S = skip for now
  set "ANS="
  set /p ANS="   > "
  if /i "!ANS!"=="S" (
    echo      Skipping - add credentials.json before first launch.
  ) else (
    goto CHECK_CREDS
  )
)

REM --- 5. .env (master sheet + optional one-click) ---------------------------
echo.
echo [5/7] Connecting your master spreadsheet...
set "RECONFIG=Y"
if exist ".env" (
  set "RECONFIG="
  echo      .env already exists.
  set /p RECONFIG="      Re-enter your settings? [y/N]: "
)
if /i "!RECONFIG!"=="Y" (
  echo.
  echo      Open your MASTER spreadsheet in your browser. The ID is the long code:
  echo        https://docs.google.com/spreadsheets/d/[ THIS LONG CODE ]/edit
  echo.
  set "MASTER_ID="
  set /p MASTER_ID="      Paste your MASTER spreadsheet ID: "
  :NEED_MASTER
  if "!MASTER_ID!"=="" (
    set /p MASTER_ID="      It can't be blank - paste the ID: "
    goto NEED_MASTER
  )
  echo.
  echo      OPTIONAL: one-click new-client generation. Leave both blank to skip
  echo      (the New-Client wizard still works the manual way). See the in-app
  echo      Help ^& Setup page, Step 4, for how to get these.
  set "WEBHOOK_URL="
  set /p WEBHOOK_URL="      Generator web app URL (ends in /exec, or Enter to skip): "
  set "WEBHOOK_SECRET="
  if not "!WEBHOOK_URL!"=="" set /p WEBHOOK_SECRET="      Generator secret (same as in the script): "
  (
    echo # Coach Abood Dashboard - local secrets ^(gitignored^). Do not commit.
    echo MASTER_SHEET_ID=!MASTER_ID!
    echo TEMPLATE_WEBAPP_URL=!WEBHOOK_URL!
    echo TEMPLATE_WEBAPP_SECRET=!WEBHOOK_SECRET!
  ) > .env
  echo      OK - saved .env
) else (
  echo      Keeping your existing .env
)

REM --- 6. Database + workout library + secrets safety ------------------------
echo.
echo [6/7] Preparing the database and workout library...
for %%E in (.env coach_data.db credentials.json token.json clients.yaml cronometer.key cronometer_creds.enc) do (
  findstr /x /c:"%%E" .gitignore >nul 2>&1 || echo %%E>> .gitignore
)
python db.py >nul 2>&1
python scripts\seed_library.py
echo      OK

REM --- 7. Desktop shortcut --------------------------------------------------
echo.
echo [7/7] Creating the "Coach Dashboard" Desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "windows\create_shortcut.ps1"
echo      OK

echo.
echo  ================================================================
echo    SETUP COMPLETE
echo  ================================================================
echo    Start the app any time by double-clicking "Coach Dashboard"
echo    on your Desktop. The browser opens at http://127.0.0.1:5000
echo    On first launch, sign in with the coaching Google account.
echo.
echo    Need help? Open the app and click "Help ^& Setup" on the left.
echo  ================================================================
echo.
set "LAUNCH="
set /p LAUNCH="   Start the dashboard now? [Y/n]: "
if /i not "!LAUNCH!"=="N" (
  start "" "windows\launch.bat"
)
endlocal
