# One-Click Client Generation — setup

This wires the **New Client** wizard so it generates the client's Google Sheet
and registers it on the dashboard automatically, instead of you running the
`Coach Tools → Generate Client Template` menu by hand.

How it works: the wizard fills the master sheet's `⚙` admin tabs (via the Sheets
API), then calls your Apps Script — deployed as a **Web App** — which runs the
exact same generator and returns the new sheet's URL. The app extracts the ID
and adds the client to the dashboard.

You set this up **once**. (It's optional — without it, the wizard falls back to
the manual menu flow.)

---

## 1. Update the Apps Script

1. Open your **master spreadsheet** → **Extensions → Apps Script**.
2. Replace the script with the contents of [`apps_script/Code.gs`](../apps_script/Code.gs)
   from this repo (it's your v6 script plus a web-app entry point — the menu
   still works exactly as before).
3. At the top, set `WEBAPP_SECRET` to a long random string, e.g.
   ```js
   const WEBAPP_SECRET = 'k7Q2-9fLp...your-own-long-random-string...';
   ```
   Save (the disk icon).

## 2. Deploy as a Web App

1. In the Apps Script editor, click **Deploy → New deployment**.
2. Click the gear ⚙ → **Web app**.
3. Set:
   - **Execute as:** *Me* (your Google account — the master sheet owner).
   - **Who has access:** *Anyone*.
   - (The secret is what actually protects it — "Anyone" only means no Google
     login is required to POST.)
4. Click **Deploy**, approve the permissions prompt, and **copy the Web app
   URL** — it ends in `/exec`.

> Re-deploy after any future script change: **Manage deployments → (edit, the
> pencil) → Version: New version → Deploy**. The `/exec` URL stays the same.

## 3. Point the dashboard at it

Open the dashboard's `.env` file and set both values:

```
TEMPLATE_WEBAPP_URL=https://script.google.com/macros/s/AKfy..../exec
TEMPLATE_WEBAPP_SECRET=k7Q2-9fLp...same-string-as-in-the-script...
```

Restart the app (close the window / re-open the shortcut).

## 4. Use it

**New Client** wizard → fill the steps → **Generate client & add to dashboard**.
The client sheet is created, shared with the client's email as Editor, and
appears on your dashboard — one click.

---

## Troubleshooting

- **"Unauthorized (bad or missing secret)"** → the secret in `.env` doesn't match
  the one in the script. Make them identical and re-deploy.
- **"Could not reach the generator web app"** → the URL is wrong, or you deployed
  with *Who has access* set to something other than *Anyone*.
- **"Program Start Date must be a valid date"** → the wizard's start date didn't
  land in `⚙ Client Info`; re-check Step 1.
- **It worked but nothing was shared** → no client email was entered in Step 1;
  share the sheet manually from Drive.
- After editing `Code.gs`, you **must** create a *New version* under Manage
  deployments or the old code keeps running.
