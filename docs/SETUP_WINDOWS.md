# Setup Guide — Windows (step by step)

This guide is written for someone who does **not** code. Follow it top to
bottom. It takes about 15 minutes the first time, and you only do it once.

When you're done you'll have a **Coach Dashboard** icon on your Desktop. Double-
click it any time to open the app in your browser.

---

## What you'll need before you start

1. **A Windows PC.**
2. **The `credentials.json` file** — Ceasar will send this to you separately
   (it is *not* inside the downloaded project, on purpose, because it's a
   secret). Save it somewhere you can find it, like your Downloads folder.
3. **Your master spreadsheet ID** — Ceasar will give you this too. It's the long
   code in the middle of the master sheet's web address:
   `https://docs.google.com/spreadsheets/d/`**`THIS-LONG-CODE`**`/edit`

---

## Step 1 — Install Python (one time)

1. Go to <https://www.python.org/downloads/> and click the big **Download
   Python** button.
2. Run the installer.
3. **IMPORTANT:** on the first screen, tick the box **"Add python.exe to PATH"**
   at the bottom, *then* click **Install Now**.
4. When it finishes, click **Close**.

## Step 2 — Download the project

1. Go to the project page: <https://github.com/ceasarattar/coach-abood-client-tracker>
2. Click the green **`< > Code`** button → **Download ZIP**.
3. Find the ZIP in your Downloads, **right-click it → Extract All… → Extract**.
4. Open the extracted folder. You should see files like `setup.bat`, `app.py`,
   and `run.py`.

## Step 3 — Add the secret file

1. Copy the **`credentials.json`** that Ceasar sent you.
2. Paste it **into the project folder** (the same folder that has `setup.bat`).

## Step 4 — Run the setup

1. In the project folder, **double-click `setup.bat`**.
   - If Windows shows a blue "Windows protected your PC" box, click **More
     info → Run anyway** (this is normal for scripts you downloaded).
2. A black window opens and runs through 8 steps. When it asks, **paste your
   master spreadsheet ID** and press Enter.
3. It finishes with **"Setup complete"** and creates a **Coach Dashboard**
   shortcut on your Desktop. Press a key to close the window.

## Step 5 — First launch & Google sign-in

1. Double-click the **Coach Dashboard** icon on your Desktop.
2. Your browser opens to the dashboard, and a **Google sign-in** tab appears.
3. Sign in with the **Google account that owns the spreadsheets** and click
   **Allow**. (If Google warns the app is "unverified", click **Advanced →
   Go to … (unsafe)** — it's your own app, it's fine.)
4. You'll land on the dashboard. Done!

> After this first sign-in, it stays signed in — you won't be asked again
> unless the login expires (then visit the **Re-auth** link, or Ceasar can flip
> the Google project to "Published" so it never expires).

---

## Using it day to day

- **Open the app:** double-click the Desktop shortcut. If it's already open, it
  just brings up the browser again — it never starts a second copy.
- **Close the app:** close the small black window that the shortcut opened.
- **Add a client:** top-right **+ Add Client**, paste the client's sheet link.
- **Workout library:** the **Library** tab already contains the PPL UL, Upper
  Lower, and Full Body programs.

---

## If something goes wrong

- **"Python is not recognized"** → you missed the *Add to PATH* tick in Step 1.
  Re-install Python and make sure that box is ticked.
- **The dashboard says "credentials.json not found"** → the secret file isn't in
  the project folder. Redo Step 3, then double-click the shortcut again.
- **A red error on a client card** → usually the sheet link is wrong or the
  signed-in Google account can't open that sheet. Check the link / sharing.
- **Anything else** → send Ceasar the file `logs\dashboard.log` from the project
  folder; it records what happened.
