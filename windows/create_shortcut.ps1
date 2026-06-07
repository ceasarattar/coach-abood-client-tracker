# Creates (or refreshes) a "Coach Dashboard" shortcut on the Desktop that
# launches the app via windows\launch.bat. Called by setup.bat; safe to re-run.
$ErrorActionPreference = "Stop"

# Project root = parent of this script's folder (windows\..).
$projectRoot = Split-Path -Parent $PSScriptRoot
$launchBat   = Join-Path $projectRoot "windows\launch.bat"
$desktop     = [Environment]::GetFolderPath("Desktop")
$shortcut    = Join-Path $desktop "Coach Dashboard.lnk"

if (-not (Test-Path $launchBat)) {
    Write-Error "launch.bat not found at $launchBat"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($shortcut)
$lnk.TargetPath       = $launchBat
$lnk.WorkingDirectory = $projectRoot
$lnk.Description       = "Coach Abood Client Tracker"
$lnk.WindowStyle       = 7   # minimized

# Use the Python interpreter's icon if available, else default.
$pyw = Join-Path $projectRoot "venv\Scripts\pythonw.exe"
if (Test-Path $pyw) { $lnk.IconLocation = $pyw }

$lnk.Save()
Write-Host "Desktop shortcut created: $shortcut"
