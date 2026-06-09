#!/usr/bin/env bash
# Coach Abood Client Tracker — LOCAL DEV setup (macOS / Linux).
# To host the app online for you + Abood, see DEPLOY.md instead.
set -euo pipefail
cd "$(dirname "$0")"

echo "================================================================"
echo "  Coach Abood Client Tracker — local dev setup"
echo "================================================================"

# 1. Python 3.10+ ------------------------------------------------------------
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && \
     "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: Python 3.10+ is required. Install from https://www.python.org/downloads/"
  exit 1
fi
echo "[1/4] Using $("$PY" --version)"

# 2. Virtual environment -----------------------------------------------------
if [ ! -d venv ]; then
  echo "[2/4] Creating virtual environment at venv/ ..."
  "$PY" -m venv venv
else
  echo "[2/4] venv/ already exists — reusing it."
fi
# shellcheck disable=SC1091
source venv/bin/activate

# 3. Dependencies ------------------------------------------------------------
echo "[3/4] Installing dependencies ..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# 4. Database (creates tables + seeds the workout library) -------------------
echo "[4/4] Preparing the local database ..."
python db.py

echo ""
echo "================================================================"
echo "  Done. Start the app:"
echo "    source venv/bin/activate"
echo "    python run.py            # http://127.0.0.1:5000"
echo ""
echo "  Connect Google Sheets locally (optional): drop service_account.json"
echo "  next to app.py and set MASTER_SHEET_ID in a .env file (.env.example)."
echo "  To host it online for you + Abood, see DEPLOY.md."
echo "================================================================"
