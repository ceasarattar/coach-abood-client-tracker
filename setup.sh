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
# Cronometer sync uses the pure-stdlib API path (cronometer_api.py) — no browser
# needed. The legacy Playwright fallback is optional; install it only if you want
# it: pip install "playwright>=1.40" && python -m playwright install chromium

# 4 & 5. .env (interactive) --------------------------------------------------
if [ -f ".env" ]; then
  echo "[4/7] .env already exists — leaving it untouched (delete it to reconfigure)."
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
  echo "  OPTIONAL one-click client generation (Enter to skip; see the in-app"
  echo "  Help & Setup page, Step 4):"
  read -r -p "  Generator web app URL (ends in /exec): " WEBHOOK_URL
  WEBHOOK_SECRET=""
  if [ -n "${WEBHOOK_URL// }" ]; then
    read -r -p "  Generator secret (same as in the script): " WEBHOOK_SECRET
  fi

  if [ ! -f "credentials.json" ]; then
    echo "  NOTE: credentials.json not found yet — get it from Ceasar and add it"
    echo "        to this folder before first launch."
  fi

  printf '# Coach Abood Dashboard — local secrets (gitignored). Do not commit.\nMASTER_SHEET_ID=%s\nTEMPLATE_WEBAPP_URL=%s\nTEMPLATE_WEBAPP_SECRET=%s\n' \
    "$MASTER_ID" "$WEBHOOK_URL" "$WEBHOOK_SECRET" > .env
  echo "[5/7] Wrote .env"
fi

# 6. .gitignore safety -------------------------------------------------------
echo "[6/7] Ensuring secrets are gitignored ..."
for entry in ".env" "coach_data.db" "credentials.json" "token.json" "cronometer.key" "cronometer_creds.enc"; do
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
