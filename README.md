# Coach Abood LLC — Client Tracker

One **hosted** Flask dashboard that you and Abood share — same URL, same data,
nothing to install on either side and nothing to keep in sync. It reads and
writes each client's Google Sheet (the source of truth) and the master
spreadsheet (Payments + admin tabs).

Three layers:

1. **Google Sheets** — each client has their own generated sheet; the master
   spreadsheet holds the admin tabs (`⚙ Client Info`, `⚙ Program Builder`,
   `⚙ Week & RIR`, `⚙ Targets`) and the `Payments` tab. Accessed via a Google
   **service account** (share each sheet with its email).
2. **Database** — a shared **Postgres** (Neon) holds the reusable workout-program
   library and the client registry. Locally it's just a SQLite file. Client
   *logs* never live here — only in Sheets.
3. **Flask app** — hosted once on **Render**, behind a shared passcode, installable
   as a desktop/phone app (PWA).

> **Deploying for real? Follow [`DEPLOY.md`](DEPLOY.md)** — the ~15-minute,
> free, one-time checklist (Neon + service account + Render). Hand Abood
> [`FOR-ABOOD.txt`](FOR-ABOOD.txt) (open a URL, click Install).

---

## How it's configured (environment variables)

Everything is driven by env vars (set in Render in production; in a local `.env`
for dev — see [`.env.example`](.env.example)):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string. Unset ⇒ local SQLite (`coach_data.db`). |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The service-account key JSON (share sheets with its email). Locally you may instead drop `service_account.json` next to `app.py`. |
| `MASTER_SHEET_ID` | The master spreadsheet id. |
| `APP_PASSCODE` | Shared login passcode. **Unset ⇒ the login gate is disabled** (local dev). |
| `SECRET_KEY` | Session signing key (Render auto-generates it). |
| `CRONOMETER_KEY` | Fernet key encrypting stored Cronometer logins (optional feature). |
| `TEMPLATE_WEBAPP_URL` / `TEMPLATE_WEBAPP_SECRET` | Optional one-click client generation. |

On startup the app **creates its tables, seeds the workout library** from
`seed/programs.json`, and **imports a legacy `clients.yaml`** if present — all
idempotent, so a brand-new database is usable immediately.

---

## Local development

```bash
git clone https://github.com/ceasarattar/coach-abood-client-tracker.git
cd coach-abood-client-tracker
./setup.sh                 # or setup.bat on Windows
source venv/bin/activate   # Windows: venv\Scripts\activate
python run.py              # opens http://127.0.0.1:5000
```

With no env vars set you get: SQLite, no login gate, and a "Sheets not connected"
state until you add a `service_account.json` (or `GOOGLE_SERVICE_ACCOUNT_JSON`)
and `MASTER_SHEET_ID`. The workout library still works fully offline.

---

## Project layout

```
app.py                Flask app (routes, page builders, login gate)
wsgi.py               production entry point (gunicorn wsgi:app)
run.py                local single-instance launcher (opens the browser)
sheets_client.py      Google Sheets API client (service-account auth)
db.py                 SQLAlchemy layer: program library + client registry + kv
secrets_store.py      encrypted Cronometer creds (stored in the DB)
seed/programs.json    the 3 shipped programs (auto-seeded on first boot)
scripts/seed_library.py   manually (re)load the library from the seed
scripts/make_icons.py     regenerate the PWA icons
render.yaml  Procfile  .python-version    hosting config (Render / any PaaS)
static/manifest.webmanifest  static/sw.js  static/icons/   PWA assets
DEPLOY.md  FOR-ABOOD.txt      deploy checklist + Abood's one-pager
templates/  static/style.css  Jinja templates + CSS
```

---

## Named ranges (read from each client sheet)

The generator creates these in every client sheet. The dashboard reads them via
`batchGet`, with an automatic A1 fallback if a range is missing:

| Named range | Range | Contents |
|---|---|---|
| `WeightDates` | `Weight!A2:A` | Date column |
| `WeightValues` | `Weight!B2:B` | Body-weight column |
| `WeightMA7` | `Weight!D2:D` | 7-day trailing average |
| `WeeklyAvg` | `Weight!E2:E` | Weekly average |
| `DailyTotal_Calories` | `Nutrition!B34` | Single cell — today's calorie total |

Daily-calorie history for the chart is read from `Weight!J` (dated by `Weight!A`),
the path the Cronometer importer populates. Payments are read from the master
sheet's `Payments` tab by A1 (`Payments!A3:I`).

---

## Routes

| Route | Description |
|---|---|
| `GET /` | Client card grid (all clients) |
| `GET /client/<name>` | Per-client detail (weight, calories, week-by-week workout log, payment) |
| `GET /library` … | Workout-program library (CRUD) |
| `GET /clients/new`, `/clients/add` | New-client wizard / register an existing sheet |
| `GET /guide` | In-app **Help & status** page |
| `GET,POST /login`, `GET /logout` | Passcode gate (active when `APP_PASSCODE` is set) |
| `GET /sw.js` | Service worker (root scope, for PWA install) |
| `GET /health` | Returns `{"status":"ok"}` (health check / keep-warm ping) |

---

## Notes

- **Sheets auth never expires:** the service account isn't subject to the old
  "Testing mode" 7-day token expiry — that whole problem is gone.
- **Seeing/fixing Abood's data:** it's the same hosted instance — open the URL. For
  raw rows, use the Neon console.
- **Logs:** rotating `logs/dashboard.log` (5 MB × 3). Stack traces never render in
  the browser. On Render, also see the service's Logs tab.
