<!-- Resuming work / picking up on another machine? Start with
     docs/PROJECT_STATUS.md — it has current state, pending steps, and how to run. -->

# Coach Abood LLC — Client Tracker

A local-only Flask web app that is the single control panel for Coach Abood.
It reads from and writes to each client's Google Sheet (the source of truth)
and the coach's master spreadsheet (Payments + admin tabs). Runs exclusively on
`http://127.0.0.1:5000`. Zero cost. Clients never access it.

Two layers:

1. **Google Sheets** — each client has their own generated sheet; the master
   spreadsheet holds the admin tabs (`⚙ Client Info`, `⚙ Program Builder`,
   `⚙ Week & RIR`, `⚙ Targets`) and the `Payments` tab.
2. **Flask dashboard** — reads/writes those sheets via the Sheets API v4.

Workout-library programs are stored locally in SQLite (`coach_data.db`), never
in the spreadsheet.

---

## Quick start (one-time setup)

**Windows (the handoff target):** see the click-by-click, no-coding-required
guide in [`docs/SETUP_WINDOWS.md`](docs/SETUP_WINDOWS.md). In short: install
Python, download the project, drop in `credentials.json`, double-click
`setup.bat`. It creates a **Desktop shortcut** — done.

**macOS / Linux (development):**

```bash
git clone https://github.com/ceasarattar/coach-abood-client-tracker.git
cd coach-abood-client-tracker
./setup.sh
source venv/bin/activate
python run.py            # single-instance launcher; opens the browser for you
```

`setup.bat` / `setup.sh` will:

1. Verify Python 3.10+ is installed.
2. Create the `venv/` virtual environment and install `requirements.txt`.
3. Prompt for your `MASTER_SHEET_ID` and write `.env`.
4. Confirm `credentials.json` is present (a secret — never committed).
5. Ensure secrets are gitignored.
6. Initialise the SQLite DB **and seed the workout library** from
   `seed/programs.json` (ships with the PPL UL, Upper Lower, Full Body programs).
7. (Windows) Create a **Coach Dashboard** Desktop shortcut.

**Launching:** use `python run.py` (or the Desktop shortcut). It is
**single-instance** — re-running it just opens the browser to the already-running
app instead of starting a second copy. `python app.py` still works for raw dev.

On first launch a browser tab opens for Google sign-in (use the Gmail with
access to the sheets). `token.json` is written and later runs are silent.

---

## Project layout

```
app.py              Flask app (routes, page builders)
run.py              single-instance launcher (use this / the shortcut)
sheets_client.py    Google Sheets API client (read + write)
db.py               SQLite workout-library layer
schema.sql          library schema
seed/programs.json  the 3 shipped programs (loaded by setup)
scripts/seed_library.py   (re)load the library from the seed
windows/            launch.bat + create_shortcut.ps1 (Windows packaging)
docs/SETUP_WINDOWS.md     non-coder setup guide
templates/  static/       Jinja templates + CSS
```

---

## Google Cloud / OAuth setup

### 1 — Create a Google Cloud project
1. <https://console.cloud.google.com> → **New Project** → name it `coach-dashboard`.
2. **APIs & Services → Library** → enable **Google Sheets API**.
3. **APIs & Services → OAuth consent screen**
   - User type: **External**, Publishing status: **Testing**
   - Add your Gmail as a **Test User**
   - Scope: `https://www.googleapis.com/auth/spreadsheets` *(read **and** write
     — the dashboard logs weight and payments back to the sheets)*
4. **Credentials → Create Credentials → OAuth client ID → Desktop app**
   - **Download JSON** → save as `credentials.json` in this folder (next to `app.py`).

### 2 — Configure the master sheet ID
`setup.sh` writes it to `.env`, or copy `.env.example` to `.env` and set:

```
MASTER_SHEET_ID=<the long ID from the master sheet's URL>
```

`https://docs.google.com/spreadsheets/d/<MASTER_SHEET_ID>/edit`

### 3 — Register clients
Edit `clients.yaml`:

```yaml
clients:
  - name: "Ceasar Attar"          # MUST match the client's row in master Payments (col A)
    spreadsheet_id: "1aBc...xyz"   # the client's own sheet ID, from its URL
    master_spreadsheet_id: ""      # blank -> uses MASTER_SHEET_ID from .env
    plan_usd: 150
    weight_unit: "kg"              # "kg" or "lbs"
    active: true
```

---

## Named ranges (read from each client sheet)

The generator creates these in every client sheet. The dashboard reads them via
`batchGet`, with an automatic A1 fallback if a range is missing:

| Named range | Range | Contents |
|---|---|---|
| `WeightDates` | `Weight!A2:A` | Date column |
| `WeightValues` | `Weight!B2:B` | Body-weight column |
| `WeightMA7` | `Weight!D2:D` | Running average (MA proxy) |
| `WeeklyAvg` | `Weight!E2:E` | Weekly average |
| `DailyTotal_Calories` | `Nutrition!B34` | Single cell — today's calorie total |

> **Removed from the old design:** `WorkoutDates`, `WorkoutCompletion`,
> `WorkoutVolume`, `CalorieTarget`, `Payment_Status_Range` — these named ranges
> do **not** exist. Workout progress is read directly from the per-week tabs
> (`Week 1` … `Week N`, client Date column = col G). Payments are read from the
> master sheet's `Payments` tab by A1 (`Payments!A3:I`).

Daily-calorie history for the chart is read from `Weight!J` (dated by
`Weight!A`); this is the path a future Cronometer importer will populate.

---

## Routes

| Route | Description |
|---|---|
| `GET /` | Client card grid (all clients) |
| `GET /client/<name>` | Per-client detail (weight, calories, week-by-week workout log, payment) |
| `GET /reauth` | Re-run OAuth flow (expired token) |
| `GET /health` | Returns `{"status":"ok"}` |

---

## Re-authentication

If the token expires, visit <http://127.0.0.1:5000/reauth>.

> **Testing-mode token expiry:** while the OAuth consent screen is in
> **Testing**, Google revokes refresh tokens after 7 days. Click **Publish App**
> on the consent screen to avoid weekly re-auth (no review needed under 100 users).

---

## Logs

Rotating log at `logs/dashboard.log` (5 MB, 3 backups). Stack traces are never
rendered in the browser.

---

## Pre-launch checklist

- [ ] `credentials.json` downloaded and placed in this folder
- [ ] `./setup.sh` (or `setup.bat`) run successfully
- [ ] `.env` contains the real `MASTER_SHEET_ID`
- [ ] `clients.yaml` updated with real client names + sheet IDs (names match master Payments col A)
- [ ] Gmail added as a Test User on the OAuth consent screen
- [ ] `python app.py` started — browser OAuth completed — `token.json` present
- [ ] <http://127.0.0.1:5000> loads and client cards appear
- [ ] `/health` returns `{"status":"ok"}`
- [ ] (Optional) OAuth consent screen published to avoid 7-day token expiry
