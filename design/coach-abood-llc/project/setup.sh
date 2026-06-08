#!/usr/bin/env bash
# Coach Abood Client Tracker — one-time setup (macOS / Linux).
# Run once after cloning:  ./setup.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "================================================================"
echo "  Coach Abood Client Tracker — Setup"
echo "================================================================"

# 1. Python 3.10+ check ------------------------------------------------------
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: Python 3.10+ is required but was not found."
  echo "Install it from https://www.python.org/downloads/ and re-run ./setup.sh"
  exit 1
fi
echo "[1/7] Using $("$PY" --version)"

# 2. Virtual environment -----------------------------------------------------
if [ ! -d "venv" ]; then
  echo "[2/7] Creating virtual environment at venv/ ..."
  "$PY" -m venv venv
else
  echo "[2/7] venv/ already exists — reusing it."
fi
# shellcheck disable=SC1091
source venv/bin/activate

# 3. Dependencies ------------------------------------------------------------
echo "[3/7] Installing dependencies from requirements.txt ..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# 4 & 5. .env (interactive) --------------------------------------------------
if [ -f ".env" ]; then
  echo "[4/7] .env already exists — leaving it untouched."
else
  echo "[4/7] Configuring .env ..."
  echo ""
  echo "  Open your MASTER spreadsheet in the browser and copy the ID from the URL:"
  echo "    https://docs.google.com/spreadsheets/d/<THIS-IS-THE-ID>/edit"
  echo ""
  read -r -p "  Paste your MASTER_SHEET_ID: " MASTER_ID
  while [ -z "${MASTER_ID// }" ]; do
    read -r -p "  MASTER_SHEET_ID cannot be empty. Paste it: " MASTER_ID
  done

  echo ""
  echo "  You also need credentials.json (OAuth Desktop app) from Google Cloud"
  echo "  Console, placed in this folder. See README.md for the click-by-click."
  read -r -p "  Is credentials.json in this folder now? [y/N]: " HAS_CREDS
  if [ ! -f "credentials.json" ]; then
    echo "  NOTE: credentials.json not found yet — add it before first launch."
  fi

  printf '# Coach Abood Dashboard — local secrets (gitignored). Do not commit.\nMASTER_SHEET_ID=%s\n' "$MASTER_ID" > .env
  echo "[5/7] Wrote .env"
fi

# 6. .gitignore safety -------------------------------------------------------
echo "[6/7] Ensuring secrets are gitignored ..."
for entry in ".env" "coach_data.db" "credentials.json" "token.json"; do
  if [ -f .gitignore ] && grep -qx "$entry" .gitignore; then :; else
    echo "$entry" >> .gitignore
  fi
done

# 7. Initialise SQLite + seed the workout library ----------------------------
echo "[7/7] Initialising database and loading the workout library ..."
python db.py
python scripts/seed_library.py

echo ""
echo "================================================================"
echo "  Setup complete."
echo ""
echo "  Next steps:"
echo "    source venv/bin/activate"
echo "    python run.py        # single-instance launcher; opens the browser"
echo ""
echo "  On first launch a browser tab opens for Google sign-in."
echo "================================================================"
