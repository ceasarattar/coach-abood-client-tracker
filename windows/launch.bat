@echo off
REM Launches the Coach Abood dashboard (single instance) and opens the browser.
REM This is what the Desktop shortcut points to. Closing this window stops the app.
cd /d "%~dp0\.."
if not exist "venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup.bat first.
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python run.py
