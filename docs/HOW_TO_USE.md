# Coach Dashboard — How to Use

A simple one-page guide.

## First-time setup (do this once before opening the app)
1. Follow the full setup guide: **[SETUP_WINDOWS.md](SETUP_WINDOWS.md)**
2. That setup installs Python, adds `credentials.json`, runs `setup.bat`, and creates the Desktop shortcut.
3. After setup is complete, come back here for day-to-day use.

---

### Open the app
- **Double-click the "Coach Dashboard" icon** on your Desktop.
- Your browser opens to the dashboard automatically.
- **First time only:** a Google sign-in tab appears — sign in with your coaching Gmail and click **Allow**. (If it warns "unverified," click **Advanced → Go to… → Allow** — it's your own app.)
- To close the app, close the little black window it opened.

### The layout
On the left you have three things:
- **Clients** — all your clients at a glance.
- **Workout Library** — your reusable programs (PPL, Upper/Lower, Full Body…).
- **Add client** — bring in a new client.

### Read a client at a glance
Each client is a card with a **colored dot**:
- 🟢 **Green** = on track  🟡 **Yellow** = needs a look  🔴 **Red** = overdue / not logging / payment late.

The card shows their **latest weight**, the **change** since last time, a mini trend line, **when they last logged a workout**, and their **payment status**. Click a card to see the full picture — weight chart, daily calories, payment details, and week-by-week workout progress.

### Add a client you already have a sheet for
1. Click **Add client**.
2. Under **"Connect an existing sheet,"** type the client's **name** and paste their **Google Sheet link**.
3. Click **Add client**. They appear on the dashboard right away.

> The name must match the client's row in your master Payments tab for payment status to show.

### Create a brand-new client from scratch
1. Click **Add client → Start guided setup**.
2. Fill the steps: their info → program → weeks & RIR → nutrition targets → review.
3. On the last step click **Generate** — the app builds their Google Sheet, shares it with their email, and adds them to your dashboard automatically.

### Log a weight or a payment for a client
1. Open the client, click **Log entry**.
2. **Weight:** enter the date (**dd/mm/yyyy**) and the weight, then **Save weight**.
3. **Payment:** enter the paid date and click **Mark paid**.

### Workout Library
Open **Workout Library** to view, **edit**, or create a **New program**. These are templates you can pull from when setting up a new client.

### If it asks you to sign in again
Logins can expire about once a week. Just click the **Re-auth** option (or re-open the app) and sign in again. *(Ceasar can make this permanent by "Publishing" the Google project.)*

---

**Something looks wrong?** A red card usually means a client's sheet link is off or not shared with your account — check the link/sharing. For anything else, send Ceasar the file `logs\dashboard.log` from the project folder.
