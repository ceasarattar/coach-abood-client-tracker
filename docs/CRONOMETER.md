# Cronometer Nutrition Sync

Pulls a client's daily calories from Cronometer into their Weight tab (col J),
which feeds the dashboard's calorie chart. Manual trigger — a button you press
whenever you want (daily/weekly).

## How it works (the reliable way)

Cronometer has **no public API**, but its own website talks to the backend over a
small, stable set of HTTP calls. `cronometer_api.py` makes the **same calls the
website makes** — no browser, so there is nothing for bot-detection to flag:

1. `GET /login/` → read the `anticsrf` token from the page.
2. `POST /login` with `anticsrf` + email + password → establishes the session
   (`sesnonce` cookie).
3. GWT-RPC `authenticate` → the numeric user id.
4. GWT-RPC `generateAuthorizationToken` → a short-lived export token.
5. `GET /export?nonce=<token>&generate=dailySummary&start=..&end=..` → CSV.

The CSV is parsed by `parse_daily_nutrition_csv` (in `cronometer_client.py`,
already unit-tested), which matches columns by name (`Date`, `Energy (kcal)`, …)
so minor export changes don't break it. Only matching dates already present in the
Weight tab are written; other dates are skipped.

### Self-healing

The one brittle part is GWT's serialization ids, which change when Cronometer
ships a new build. They're pinned in the `CONFIG` block of `cronometer_api.py`
**and** auto-recovered: if the token step fails, the client re-reads the current
`AuthScope` id out of Cronometer's compiled JS and retries once. If a future
Cronometer change breaks login or `authenticate` outright, the sync surfaces a
clear message — update the pinned constants in `cronometer_api.py`.

### Old browser path (fallback only)

`cronometer_client.fetch_daily_nutrition` (Playwright) is kept as a manual
fallback and as the home of the tested CSV parser. It is **not** used by the app
anymore — the direct API above replaced it because the GWT diary UI was
unreliable to scrape and looked bot-like.

## How credentials are handled

Each client's Cronometer email + password are stored **encrypted at rest**
(`cronometer_creds.enc`, key in `cronometer.key`) — both gitignored, both local
to the coach's machine. Passwords are never put in the Google Sheet, the
database, the dashboard config, or GitHub.

> This is encryption at rest, not a vault. Anyone with access to the unlocked
> Windows account can use the app. Treat the machine accordingly.

## Setup / use

1. In the app: open a client → **Cronometer** → enter their Cronometer email +
   password → **Save credentials**.
2. Click **Sync nutrition**. Calories for matching dates are written to the
   Weight tab; dates with no existing row are skipped.

> 2-factor authentication: if a client's Cronometer account has 2FA enabled the
> automated sync can't pass it — the app says so. Turn off 2FA for that account
> to use sync.

### Validate from the command line

```
python cronometer_api.py "Client Name"   # uses the saved encrypted login
```

Prints how many days parsed and the last few dates + calories. No browser needed.

## Files

- `cronometer_api.py` — direct HTTP/GWT-RPC fetch (**primary**, no browser).
- `cronometer_client.py` — `parse_daily_nutrition_csv` (tested) + Playwright fallback.
- `secrets_store.py` — encrypted credential storage (tested).
- `nutrition_sync.py` — writes calories into `Weight!J` by date (tested logic).
- Route `/client/<name>/cronometer` + `templates/client_cronometer.html`.
