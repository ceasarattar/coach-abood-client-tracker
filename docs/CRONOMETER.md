# Cronometer Nutrition Sync

Pulls a client's daily calories from Cronometer into their Weight tab (col J),
which feeds the dashboard's calorie chart. Manual trigger — a button you press
whenever you want (daily/weekly).

## Why it works this way

Cronometer has **no public API** (confirmed — see the project notes). The most
robust route is to drive Cronometer's own **CSV export** with a headless browser
(Playwright) and parse the result, rather than scraping the live page DOM. The
parser matches columns by name, so small export changes don't break it.

## How credentials are handled

Each client's Cronometer email + password are stored **encrypted at rest**
(`cronometer_creds.enc`, key in `cronometer.key`) — both gitignored, both local
to the coach's machine. Passwords are never put in the Google Sheet, the
database, the dashboard config, or GitHub.

> This is encryption at rest, not a vault. Anyone with access to the unlocked
> Windows account can use the app. Treat the machine accordingly.

## Setup

1. Ensure the browser is installed (the setup script does this; or run it once):
   ```
   python -m playwright install chromium
   ```
2. In the app: open a client → **Cronometer** → enter their Cronometer email +
   password → **Save credentials**.
3. Click **Sync nutrition**. Calories for matching dates are written to the
   Weight tab; dates with no existing row are skipped.

## ⚠️ One validation step (important)

The browser login/export steps in `cronometer_client.py` are **best-effort and
need one real-account test** — Cronometer's UI changes over time. Everything
breakable lives in the `CONFIG` block at the top of that file (URLs + selectors)
and in `_trigger_daily_export()`. To validate:

```python
# from the project folder, with a real test account:
python -c "import cronometer_client as c; \
import json; print(json.dumps(c.fetch_daily_nutrition('EMAIL','PASSWORD',days=7,headless=False), indent=2))"
```

`headless=False` opens a visible browser so you can see exactly where it stops,
then adjust the selectors in the CONFIG block. The CSV parser itself is already
unit-tested and correct.

## Files

- `secrets_store.py` — encrypted credential storage (tested).
- `cronometer_client.py` — Playwright login + CSV export + `parse_daily_nutrition_csv` (parser tested; browser steps need validation).
- `nutrition_sync.py` — writes calories into `Weight!J` by date (tested logic).
- Route `/client/<name>/cronometer` + `templates/client_cronometer.html`.
