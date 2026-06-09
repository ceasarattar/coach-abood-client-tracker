# Handoff — hosted dashboard

The app is now **hosted once** and shared. Handoff is no longer "send Abood a
folder + secret files" — it's "deploy once, then send a link."

---

## 1. Deploy it (you, one time)

Follow **[`DEPLOY.md`](DEPLOY.md)** — Neon Postgres + a Google service account +
Render, all free, ~15 minutes. You set six environment variables; the app creates
its tables and seeds the workout library on first boot.

## 2. Give it to Abood

Send him **the URL + the passcode** and the file **[`FOR-ABOOD.txt`](FOR-ABOOD.txt)**.
He opens the link, types the passcode, and optionally clicks **Install** to get a
desktop app. Nothing to download, no Python, no `credentials.json`.

---

## 3. ⚠️ Redeploy the Apps Script (one-time, fixes the Weight tab)

Unchanged by the hosting move. The Weight-tab fix (correct **Week #** + averages,
`dd/mm/yyyy` dates) lives in `apps_script/Code.gs` (**v8**). The generator that
builds client sheets is the copy **deployed inside the master spreadsheet** — update
it once:

1. Master sheet → **Extensions → Apps Script**.
2. Replace everything with the new `apps_script/Code.gs` (keep your `WEBAPP_SECRET`).
3. **Manage deployments → (pencil) Edit → Version: New version → Deploy.**

Until you do this, *newly generated* client sheets keep the old broken Week numbers.

---

## 4. Secrets — where they live now

No secret files are shipped or committed. Everything sensitive is a **Render
environment variable**:

| Secret | Where | Notes |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Render env | Share every sheet with its `client_email`. Rotate by creating a new key in Cloud Console. |
| `DATABASE_URL` | Render env | Neon connection string. |
| `APP_PASSCODE` | Render env | Shared login. Change it → Render redeploys. |
| `SECRET_KEY` | Render env | Auto-generated. |
| `CRONOMETER_KEY` | Render env | Fernet key. Changing it makes saved Cronometer logins unreadable (re-enter them). |
| `MASTER_SHEET_ID`, `TEMPLATE_WEBAPP_*` | Render env | Sheet id + optional one-click generation. |

The old `credentials.json` / `token.json` / `cronometer.key` / `cronometer_creds.enc`
files are **no longer used**. If they ever existed on a machine and were shared,
the only live secret to rotate is the service-account key.

---

## 5. Pre-flight checklist

- [ ] `apps_script/Code.gs` (v8) pasted into the master sheet **and re-deployed**.
- [ ] Neon DB created; `DATABASE_URL` set in Render.
- [ ] Service account created; `GOOGLE_SERVICE_ACCOUNT_JSON` set; **master + every
      client sheet shared** with its email (Editor).
- [ ] `MASTER_SHEET_ID`, `APP_PASSCODE` (and `CRONOMETER_KEY` if used) set in Render.
- [ ] Deployed; URL loads; passcode works; client cards + library appear.
- [ ] Abood has the URL + passcode + `FOR-ABOOD.txt`.
- [ ] (Optional) UptimeRobot pings `/health` every 10 min to avoid cold starts.
- [ ] (Optional) Cronometer: saved a client's login and **Sync nutrition** worked.
