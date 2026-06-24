# Migration Runbook — Coach Khader

This document covers the **manual Google-side steps** required to complete the
Coach Khader rebrand. None of these steps can be automated from git — they must
be performed by the coach (or whoever owns the Google account).

---

## A. Redeploy the Apps Script (required for all changes)

The file `apps_script/Code.gs` in this repo is **not** the running copy.
The live copy lives in the Apps Script editor bound to the master sheet.
Every code change requires this redeploy.

1. Open the **master Google Sheet**.
2. **Extensions → Apps Script** to open the script editor.
3. Replace the entire contents of `Code.gs` with the contents of
   `apps_script/Code.gs` from this repo.
   - Keep the existing values of `WEBAPP_SECRET` and `SERVICE_ACCOUNT_EMAIL`
     (copy them from the editor before replacing).
4. **Deploy → Manage deployments → (pencil) Edit → New version → Deploy**.
   - If you create a *new* deployment instead: copy the new `/exec` URL and
     update `TEMPLATE_WEBAPP_URL` in Render's environment variables.
5. Run **Coach Tools → Run First-Time Setup** once.
   - This sets the master sheet's locale to `en_GB` (dd/MM/yyyy), fixing date
     entry in the master's admin tabs.

---

## B. Transfer the master sheet to Coach Khader's Gmail

This moves ownership so client sheets and emails come from Coach Khader.
The Google Cloud service account (read path) is **not affected** — leave it as-is.

### Step 1 — Transfer sheet ownership

1. Open the **master Google Sheet**.
2. **Share** (top-right) → type Coach Khader's Gmail → set role **Editor** → Send.
3. In the Share dialog, find Coach Khader's email → click their role dropdown →
   **Transfer ownership** → confirm.
4. Coach Khader accepts the ownership transfer from their Gmail.

> The Apps Script bound to the master sheet transfers with it — it is now
> associated with Coach Khader's account.

### Step 2 — Redeploy the script as Coach Khader

1. Coach Khader opens the master sheet → **Extensions → Apps Script**.
2. **Deploy → New deployment**:
   - Type: **Web app**
   - Execute as: **Me** (Coach Khader's account)
   - Who has access: **Anyone**
3. Authorize when prompted (Coach Khader grants permissions to send email,
   create sheets, etc. on their behalf).
4. Copy the new `/exec` URL.

### Step 3 — Update Render

1. Go to the Render dashboard → your service → **Environment**.
2. Update `TEMPLATE_WEBAPP_URL` to the new `/exec` URL from Step 2.
3. Leave `TEMPLATE_WEBAPP_SECRET` unchanged (it must match `WEBAPP_SECRET` in Code.gs).
4. Render will restart the service automatically.

### Step 4 — Verify

- Go to the dashboard → **New client setup** → complete a test client.
- The generated sheet should be owned by Coach Khader's Gmail.
- The notification email to the client should come from Coach Khader's Gmail.

---

## C. Existing client sheets (optional)

Existing client sheets remain owned by the original Gmail account — they still
read fine via the service account. Transfer individually from Google Drive only
if desired:

- Drive → right-click the file → **Share** → add Coach Khader as Editor →
  Transfer ownership.

---

## D. Post-migration checklist

- [ ] Apps Script redeployed from `apps_script/Code.gs` (v9)
- [ ] First-Time Setup run (master locale → `en_GB`)
- [ ] Master sheet ownership transferred to Coach Khader's Gmail
- [ ] Apps Script redeployed as Coach Khader (new `/exec` URL)
- [ ] `TEMPLATE_WEBAPP_URL` updated on Render
- [ ] Test generation: one new client sheet generated, owned by Coach Khader
- [ ] Test notification: client receives email from Coach Khader's Gmail
- [ ] Verify sheet link opens without a Google account (ANYONE_WITH_LINK)
