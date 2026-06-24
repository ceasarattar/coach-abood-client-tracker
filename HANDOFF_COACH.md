# Coach Khader Dashboard — Transfer Guide

## What you're transferring
A Flask dashboard hosted on Render (free tier) at `https://coach-abood.onrender.com`. It reads/writes Google Sheets via a service account. Coach generates client sheets via an Apps Script web app. Currently the service account and Apps Script are under **Ceasar's** Google account — this guide moves everything to Coach Khader's ownership.

---

## Step 1 — Coach Khader creates his own Google Cloud service account

This is the credential the dashboard uses to read client sheets. He needs to own it.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → sign in with his Gmail
2. Click **Select a project** (top bar) → **New Project** → name it anything (e.g. "Coach Khader Dashboard") → **Create**
3. Left sidebar → **APIs & Services → Library**
   - Search **Google Sheets API** → Enable
   - Search **Google Drive API** → Enable
4. Left sidebar → **IAM & Admin → Service Accounts → + Create Service Account**
   - Name: `dashboard-reader` (or anything)
   - Click through the role steps (no role needed) → Done
5. Click the service account → **Keys tab → Add Key → JSON**
6. A `.json` file downloads — **send that file to Ceasar securely** (this is the credential)

---

## Step 2 — Share the master Google Sheet with the new service account

1. Open the downloaded JSON file, find the `"client_email"` field — looks like `dashboard-reader@his-project.iam.gserviceaccount.com`
2. Open the master Google Sheet → Share → paste that email → **Viewer** access → Send

---

## Step 3 — Coach Khader sets up Apps Script (sheet generator)

1. Open his master Google Sheet → **Extensions → Apps Script**
2. Delete all existing code in the editor
3. Copy the full contents of `apps_script/Code.gs` from the repo and paste it in
4. Fill in the two constants at the very top of the file:
   ```js
   const WEBAPP_SECRET = 'paste-the-value-of-TEMPLATE_WEBAPP_SECRET-from-render-here';
   const SERVICE_ACCOUNT_EMAIL = 'his-service-account@project.iam.gserviceaccount.com';
   ```
5. **Deploy → New deployment**
   - Type: **Web app**
   - Execute as: **Me** (Coach Khader)
   - Who has access: **Anyone**
   - Click Deploy → copy the `/exec` URL
6. Run **firstTimeSetup**: in the script editor, select `firstTimeSetup` from the function dropdown → Run (sets master sheet locale to dd/mm/yyyy)

---

## Step 4 — Ceasar updates Render environment variables

Go to [render.com](https://render.com) → coach-abood service → **Environment**:

| Variable | New value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full contents of Coach Khader's downloaded JSON file (paste the whole thing) |
| `TEMPLATE_WEBAPP_URL` | The `/exec` URL from Step 3 |
| `APP_PASSCODE` | Set a new passcode for Coach Khader to log in with |

Click **Save** — Render restarts automatically (~30 seconds).

---

## Step 5 — Smoke test together

1. Visit `https://coach-abood.onrender.com` → log in with the new passcode
2. Add a test client through the full 6-step wizard
3. Confirm: sheet appears in **Coach Khader's** Google Drive named `[Name] — Coach Khader`
4. Confirm: client received an email notification with the sheet link
5. Confirm: dashboard can read the sheet (go to the client's page — charts render after a few seconds)

---

## Step 6 — Clean up Ceasar's test Apps Script (optional)

Delete or disable the test Apps Script deployment created under Ceasar's Google account during testing. Coach Khader's deployment is now live.

---

## Ownership summary

| Thing | Owner |
|---|---|
| GitHub repo (`coach-abood-client-tracker`) | Ceasar |
| Render service (`coach-abood.onrender.com`) | Ceasar |
| Google Cloud project + service account | Coach Khader |
| Apps Script project | Coach Khader (inside his master sheet) |
| Master Google Sheet | Coach Khader |
| Generated client sheets | Coach Khader's Google Drive |
| Neon Postgres database | Check `DATABASE_URL` on Render for the connection owner |
