# Deploy the Coach Abood dashboard (one time, ~15 minutes, free)

This hosts the app **once** so you and Abood open the same URL and share the same
data. Nothing to install on Abood's PC, nothing to sync. Do this once; after that
you only ever `git push` and Render redeploys automatically.

Free stack: **Render** (web app) + **Neon** (Postgres) + a Google **service
account** (Sheets). You'll set six environment variables. Have the repo pushed to
GitHub first.

> Tip: keep a scratch note open and paste each value you copy (DATABASE_URL, the
> service-account email, etc.) as you go — you'll paste them all into Render at the end.

---

## 1. Database — Neon Postgres (free)

1. Go to **neon.tech** → sign in with GitHub → **Create project** (any name, any region).
2. On the project dashboard, copy the **connection string** (it looks like
   `postgresql://user:password@ep-xxxx.aws.neon.tech/neondb?sslmode=require`).
3. Save it as **`DATABASE_URL`**.

(The app creates its tables and seeds the workout library automatically on first
boot — you don't run any SQL.)

---

## 2. Google service account — replaces the old login (never expires)

1. **console.cloud.google.com** → pick your existing project (the one with the sheets).
2. **APIs & Services → Library** → search **Google Sheets API** → **Enable**.
3. **APIs & Services → Credentials → Create credentials → Service account.**
   Name it `coach-dashboard`, click **Done**.
4. Click the new service account → **Keys → Add key → Create new key → JSON →
   Create**. A `.json` file downloads. Open it in a text editor and copy the
   **entire contents** — that's **`GOOGLE_SERVICE_ACCOUNT_JSON`**.
5. From that file (or the service-account list) copy the **`client_email`** —
   it looks like `coach-dashboard@your-project.iam.gserviceaccount.com`.

### Share the sheets with it
For the **master sheet** and **every client sheet**: open it → **Share** → paste
the service-account email → give it **Editor** → Send. (No invite email is needed;
the robot account just needs access.)

> This is the whole "login" fix: the app now authenticates as this robot account,
> so there's no `credentials.json`, no browser sign-in, and no weekly expiry.

---

## 3. Pick your secrets

- **`MASTER_SHEET_ID`** — the long code in the master sheet URL
  (`docs.google.com/spreadsheets/d/`**THIS**`/edit`).
- **`APP_PASSCODE`** — any phrase you and Abood will type to log in (e.g. a 2-word phrase).
- **`CRONOMETER_KEY`** — only if you use Cronometer sync. Generate one:
  ```
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `SECRET_KEY` is generated automatically by Render (see render.yaml). You don't set it.
- Optional: **`TEMPLATE_WEBAPP_URL`** / **`TEMPLATE_WEBAPP_SECRET`** if you use
  one-click client generation (same values as before).

---

## 4. Render — deploy the web app (free)

1. Go to **render.com** → sign in with GitHub.
2. **New → Blueprint** → pick the `coach-abood-client-tracker` repo. Render reads
   `render.yaml` and creates the web service. (Or **New → Web Service** and set
   Build = `pip install -r requirements.txt`, Start =
   `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`.)
3. Open the service → **Environment** → add each variable from steps 1–3:
   `DATABASE_URL`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `MASTER_SHEET_ID`, `APP_PASSCODE`,
   `CRONOMETER_KEY`, and the optional `TEMPLATE_WEBAPP_*`. (`SECRET_KEY` is already
   there, auto-generated.)
4. **Save** → Render deploys. When it's live you get a URL like
   `https://coach-abood.onrender.com`.

---

## 5. Verify & hand off

1. Open the URL → enter the **passcode** → you should see the client cards and,
   under **Workout Library**, your 3 programs.
2. Open a client card to confirm the sheet data loads. If a card shows an access
   error, that sheet isn't shared with the service-account email (step 2).
3. **Send Abood the URL + the passcode.** Tell him: open it, then in Edge/Chrome
   click **⋯ → Apps → Install this site as an app** to get a desktop icon. (Also in
   `FOR-ABOOD.txt`.)

That's it — you both now use the same live dashboard. To change anything later,
edit code and `git push`; Render redeploys on its own.

---

## Notes

- **Cold starts:** Render's free tier sleeps after ~15 min idle; the first hit
  then takes ~30–60s. To keep it warm, create a free monitor at **uptimerobot.com**
  (or **cron-job.org**) that pings `https://YOUR-URL/health` every 10 minutes.
- **Seeing/fixing Abood's data:** it's the *same* instance — just open the URL. For
  raw data, the Neon dashboard has a SQL/table browser for the library + clients.
- **No-sleep alternative:** Fly.io stays awake on its free allowance but requires a
  credit card on file. The code already works there (`Procfile` + `gunicorn`).
- **Rotating the passcode / keys:** change the env var in Render → it redeploys.
  Changing `CRONOMETER_KEY` makes previously-saved Cronometer logins unreadable
  (just re-enter them).
