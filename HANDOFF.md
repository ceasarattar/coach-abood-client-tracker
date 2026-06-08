# Handoff to Coach Abood — checklist & secrets

Everything needed to hand this app to Abood and keep it running. Two audiences:
**what Abood does** (non-coder, Windows) and **what Ceasar provides/rotates**.

---

## 1. What to send Abood (the 3 things)

The GitHub download contains the app but **no secrets**. Send these separately:

| Item | What it is | Where Abood puts it |
|---|---|---|
| `credentials.json` | Google OAuth *Desktop app* key (Sheets API enabled) | the project folder (next to `setup.bat`) |
| **Master spreadsheet ID** | the long code in the master sheet URL | pasted when `setup.bat` asks |
| Repo link | https://github.com/ceasarattar/coach-abood-client-tracker | he clicks Code → Download ZIP |

Optional (for one-click new-client generation):

| Item | What it is |
|---|---|
| `TEMPLATE_WEBAPP_URL` | the Apps Script Web App `/exec` URL |
| `TEMPLATE_WEBAPP_SECRET` | the matching secret string |

Abood's path: read `START_HERE.txt` → install Python → drop in `credentials.json`
→ double-click `setup.bat` → sign in once. The in-app **Help & Setup** page shows
a live checklist of what's done.

---

## 2. ⚠️ Redeploy the Apps Script (one-time, fixes the Weight tab)

The Weight-tab fix (correct **Week #** + averages, no more `#VALUE!`, day/month/year
dates) lives in `apps_script/Code.gs` (**v8**). The repo is the source of truth, but
the generator that actually builds client sheets is the copy **deployed inside the
master spreadsheet**. Update it once:

1. Master sheet → **Extensions → Apps Script**.
2. Replace everything with the new `apps_script/Code.gs` (keep your `WEBAPP_SECRET`).
3. **Manage deployments → (pencil) Edit → Version: New version → Deploy.**

Until you do this, *newly generated* client sheets keep the old broken Week numbers.
(Already-generated sheets can be regenerated, or fixed by hand — the bug was only in
the `Week #` / `Running Avg` formulas.)

---

## 3. Secrets — what to rotate / verify

Nothing secret is in git (verified: `credentials.json`, `token.json`, `.env`,
`clients.yaml`, `cronometer.key`, `cronometer_creds.enc`, `coach_data.db`, `logs/`
are all gitignored). Still, before/at handoff:

- **`WEBAPP_SECRET`** (in `apps_script/Code.gs` + `.env`): the committed file ships a
  placeholder `CHANGE_ME_to_a_long_random_secret`. Make sure the **deployed** script
  and the `.env` both use the *same long random* value — and a fresh one for the
  handoff. Re-deploy after changing it.
- **`credentials.json` / `token.json`**: if these ever left a shared channel, rotate
  the OAuth client in Google Cloud Console and re-download `credentials.json`.
- **Cronometer logins**: stored encrypted per-client on Abood's machine
  (`cronometer_creds.enc` + `cronometer.key`). They never leave the PC. If the PC
  changes hands, delete those two files.

## 4. Stop the weekly Google re-login (recommended)

While the OAuth consent screen is in **Testing**, Google kills the refresh token
~weekly (Abood would re-sign-in). Fix permanently: Google Cloud Console → OAuth
consent screen → **Publish App** (no review needed under 100 users).

---

## 5. Pre-flight checklist

- [ ] `apps_script/Code.gs` (v8) pasted into the master sheet **and re-deployed**.
- [ ] `WEBAPP_SECRET` is a fresh long random value in both the script and `.env`.
- [ ] OAuth consent screen **Published** (or accept weekly re-auth).
- [ ] `credentials.json` sent to Abood; master sheet ID sent.
- [ ] Abood ran `setup.bat`, signed in, dashboard loads, client cards appear.
- [ ] (Optional) one-click generation: `TEMPLATE_WEBAPP_URL`/`SECRET` in `.env`.
- [ ] (Optional) Cronometer: saved a client's login and **Sync nutrition** worked.
- [ ] Delete the two orphaned test sheets from Drive if not already gone
      (`Coach Abood — Coach Abood LLC`, `ZZ E2E Test — Coach Abood LLC`).

---

## 6. Verified working (this pass)

- Weight-tab formulas fixed and **proven on a live Sheet**: Week # correct, no
  `#VALUE!`/`#ERROR!`; new client sheets use a day-first (en_GB) locale and
  `dd/MM/yyyy` everywhere (Weight, Nutrition, Week-tab dates).
- Cronometer sync **rebuilt** (`cronometer_api.py`, no browser, no bot detection) and
  tested end-to-end against a real account — login → token → CSV export → calories
  written to `Weight!J`.
- Dashboard routes (`/`, `/client/<name>`, `/library`, `/clients/new`,
  `/clients/add`, `/client/<name>/cronometer`, `/guide`, `/health`) all return 200.
- Onboarding: `START_HERE.txt`, guided `setup.bat`, and an in-app **Help & Setup**
  page with a live status checklist.
