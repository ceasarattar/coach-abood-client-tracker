# Coach Khader Dashboard — Claude Code Session Handoff

## Project overview
Flask dashboard for a personal training coach. Tracks clients, generates Google Sheets programs, integrates Cronometer nutrition data. Built and maintained by Ceasar Attar for Coach Khader.

**Repo:** `https://github.com/ceasarattar/coach-abood-client-tracker`
**Live URL:** `https://coach-abood.onrender.com`
**Working directory:** `/Users/ceasarattar/Code/Coach Abood LLC/coach_dashboard/`
**Branch:** `main` (auto-deploys to Render — pushing main = deploying live)

---

## Stack
- **Backend:** Flask 3.x, gunicorn, Python 3.12
- **Database:** SQLite locally / Neon Postgres on Render via `DATABASE_URL` (SQLAlchemy 2.x)
- **Sheets:** Google Sheets API via service account (`GOOGLE_SERVICE_ACCOUNT_JSON` env var); `sheets_client.py` wraps the Google API client
- **Sheet generation:** Apps Script web app (config-in-POST pattern); `apps_script/Code.gs` is the source of truth but must be manually pasted into Google's editor and redeployed by a human
- **Hosting:** Render free tier (512MB RAM, single instance)
- **Auth:** shared passcode (`APP_PASSCODE`); CSRF on all POST forms via session token

---

## What was built (9 phases + redesign)

- **Phase 1:** TTL cache (`cache.py`) with anti-stampede + stale-on-error; global error handlers (404/500 pages)
- **Phase 2:** Client CRUD — edit, toggle active, delete routes + `client_edit.html`
- **Phase 3:** Flatpickr date picker vendored offline (dd/mm/yyyy everywhere, `disableMobile:true`)
- **Phase 4:** Dynamic workout sessions — `session_label[]` form array replacing fixed Mon–Sun grid; config-in-POST to Apps Script; `_build_config_payload()` helper; Apps Script v9 (idempotency via requestId, trash-on-error, ANYONE_WITH_LINK sharing, client email notification)
- **Phase 5:** Rebrand Coach Abood → Coach Khader; CSRF protection (`_csrf_token()`, `_check_csrf()` before_request, `{{ csrf_input() }}` in all POST forms)
- **Phase 6:** pytest suite — 55 tests in `tests/` (unit + integration, in-memory SQLite)
- **Phase 7:** Docs (`MIGRATION_COACH_KHADER.md`, `DESIGN_PROMPT.md`)
- **UI Redesign:** "Studio" warm-paper light theme — oklch CSS variables, indigo accent, traffic-light status. `style.css` + all templates updated. PWA manifest + service worker cache version bumped.

---

## Architecture decisions — do not revert without good reason

### Single gunicorn thread (`--workers 1 --timeout 120`, no `--threads`)
Render free tier has 512MB RAM. The Google API Python client is heavy. With 2+ threads, concurrent Sheets API calls each held large JSON responses in memory simultaneously → OOM crashes → 502 errors on every page nav. Dropping to 1 thread (fully sequential) eliminated this. The app is single-coach, low concurrency — sequential handling is fine. Start command is in `render.yaml`.

### No ThreadPoolExecutor
Previously used `ThreadPoolExecutor(max_workers=N)` with per-thread Google API services (httplib2 thread-safety requirement). Removed entirely — the pool was the primary OOM trigger on cold dashboard loads. If threads are ever re-introduced, each thread MUST use its own Google API service instance — see the old `_thread_service()` / `_thread_local` pattern as a reference.

### TTL cache capped at 100 entries (`cache.py`)
Cache had no size limit, causing slow memory growth over long sessions. Now evicts the soonest-to-expire entry when over 100 keys.

### Service account JSON parsed once (`sheets_client.py`)
`_sa_info_cache` caches the parsed service account dict on first call. Subsequent `authenticate()` calls return the cached service without re-parsing the env var JSON.

### Apps Script timeout 90s (not 120s)
Gunicorn worker timeout is 120s. If Apps Script took longer, gunicorn killed the worker before Flask could catch the error → 502 instead of a user-facing flash message. 90s ensures Flask's `except` block runs first.

### Sequential client loading on dashboard index
`cards = [make_card(c) for c in clients]` — intentionally sequential. Previously `_POOL.map(make_card, clients)` ran all client Sheets reads in parallel and spiked memory on every cold start.

---

## Key files

| File | Purpose |
|---|---|
| `app.py` | Main Flask app (~1300 lines). All routes, CSRF, wizard, client CRUD, cache integration |
| `sheets_client.py` | Google Sheets API wrapper. Service account auth, data fetchers, per-sheet helpers |
| `cache.py` | TTL cache with 100-entry cap, stale-on-error, per-key anti-stampede locks |
| `db.py` | SQLAlchemy models, bootstrap, client/program/KV CRUD |
| `secrets_store.py` | Fernet-encrypted Cronometer credential storage |
| `apps_script/Code.gs` | Apps Script v9 source. NOT the running copy — must be manually pasted and redeployed |
| `render.yaml` | Render config. `autoDeploy: true` from `main` |
| `static/style.css` | Full "Studio" light theme. oklch CSS vars, all 32 variables defined |
| `static/sw.js` | Service worker, cache version `coach-khader-v2`, network-first strategy |
| `static/manifest.webmanifest` | PWA config, light theme colors |
| `static/vendor/` | Flatpickr vendored offline (flatpickr.min.js, flatpickr.min.css) |
| `templates/base.html` | Base layout. Loads flatpickr light CSS, sets theme-color |
| `templates/client_new.html` | 6-step wizard. Dynamic session rows (`name="session_label"`), `lockSubmit()` |
| `templates/library_edit.html` | Program editor. Dynamic sessions, datalist clear-on-focus fix |
| `tests/conftest.py` | pytest fixtures — in-memory SQLite, `_make_form` multi-value helper |
| `tests/test_logic.py` | 15 unit tests for `_parse_program_form`, `_build_config_payload`, `_parse_wizard_form` |
| `tests/test_routes.py` | 40 integration tests — routes, branding, CSRF, library CRUD, wizard, error pages |
| `HANDOFF_COACH.md` | Step-by-step guide for transferring to Coach Khader |
| `MIGRATION_COACH_KHADER.md` | Apps Script redeploy + ownership transfer runbook |

---

## Critical constraints

- **Pushing `main` auto-deploys to Render.** Never push broken code to `main`. Use a branch.
- **`apps_script/Code.gs` in the repo is NOT the running copy.** Editing it changes nothing in production until a human pastes it into the Apps Script editor and clicks Deploy → New version.
- **httplib2 is not thread-safe.** If threads are ever re-introduced, each thread MUST have its own Google API service instance. Do not share the global `_service_cache` across threads.
- **Never touch the Drive file on client delete** — only remove from the SQLite/Postgres DB and clear the cache. The Google Sheet stays in Drive.
- **`WEBAPP_SECRET` in Code.gs must match `TEMPLATE_WEBAPP_SECRET` on Render.** Mismatch causes silent `{"ok": false, "error": "Unauthorized"}` on every sheet generation attempt.
- **Render free tier sleeps after inactivity.** cron-job.org is configured to ping `/health` (GET) every 10 minutes to keep the instance warm. UptimeRobot is also running but uses HEAD requests which may not count for Render's sleep timer.

---

## Running locally

```bash
cd "/Users/ceasarattar/Code/Coach Abood LLC/coach_dashboard"
venv/bin/flask --app app run --port 5101
# Open http://127.0.0.1:5101
```

- `.env` has `MASTER_SHEET_ID` set; `APP_PASSCODE` unset = login gate disabled
- `TEMPLATE_WEBAPP_URL` unset = sheet generation disabled locally (shows manual fallback)
- `credentials.json` is an OAuth client file (not a service account); `token.json` holds the cached OAuth token for local Sheets auth

## Running tests

```bash
cd "/Users/ceasarattar/Code/Coach Abood LLC/coach_dashboard"
venv/bin/python -m pytest tests/ -v
# All 55 tests should pass in ~0.4s
```

---

## Pending / not yet done

- **Service account transfer:** currently under Ceasar's Google account. Coach Khader needs to create his own (see `HANDOFF_COACH.md`).
- **Apps Script transfer:** test deployment was under Ceasar's account. Coach Khader deploys from his own master sheet.
- **Cronometer and live generation** can only be tested with Coach Khader's real credentials — not testable locally or with test accounts.
- **Windows Chrome on Ceasar's machine** has a cached bad state (service worker cached a 502). Works fine in incognito and on all other devices. Not a code issue.
