# DESIGN_PROMPT.md — UI Redesign Brief for Next Session

Paste the prompt below (everything between the `---` dividers) into a new
Claude Code session to redesign the dashboard UI. Attach the files listed in
the "Attach" section before sending.

---

## Attach these files before sending this prompt

```
coach_dashboard/templates/          ← all .html files
coach_dashboard/static/style.css
coach_dashboard/static/vendor/flatpickr.min.css
coach_dashboard/static/vendor/flatpickr-dark.css
coach_dashboard/CONTINUE_HERE.md   ← architecture reference
```

Also take and attach screenshots of each page listed in the data inventory
below (run the app locally with `./venv/bin/python -m flask --app app run`
and screenshot: index, client detail, nutrition, log, wizard step 2, library).

---

## The Prompt (copy everything below this line)

Use the **impeccable** skill to redesign the entire Coach Khader dashboard UI.

### Goals

- **Simple, elegant, easy to interpret** — a coach should be able to read a
  client's status at a glance without cognitive load.
- **Fully responsive** — works on desktop, tablet, and phone.
- **Dark UI** — keep the existing dark palette as the primary theme.
- **Preserve 100% of current functionality and data** — do not water down,
  remove, or collapse any information that currently exists on any page.
  Every number, label, chart, and control must remain visible and usable.
- **Brand: Coach Khader** — the sidebar brand mark is "CK", brand name is
  "Coach Khader".

### What NOT to change

- **Plotly charts** — keep them. Do not replace with a different chart library.
- **flatpickr** — keep it for all date inputs (`.js-date` class, dd/mm/yyyy).
- **Route names and Jinja variable names** — the backend must keep working
  without changes. Only edit `.html` files and `style.css`.
- **CSRF tokens** — every POST form has `{{ csrf_input() }}`. Keep them.

### Per-page data inventory (preserve ALL of this)

#### `/` → `index.html`
Client cards, one per active client:
- Status dot (green/amber/red based on last workout recency)
- Client name
- Latest weight + delta from previous entry
- 7-point weight sparkline
- Last logged workout (date + days ago)
- Payment badge (paid / overdue / unknown)
- "Needs attention" filter toggle (shows only clients with issues)

#### `/client/<name>` → `client.html`
- Stat strip (5 panels): latest weight, 30-day weight change, last workout
  (days ago + date), avg calories (30 days), avg sleep (7 nights)
- Weight chart: 30-day line + 7-day moving average overlay (Plotly)
- Calorie chart: 30-day bar/line (Plotly) + link to Full Nutrition View
- Payment panel: all columns from the master Payments tab (plan, last paid,
  next due, status)
- Workout log: week-by-week session completion bars (week, logged/total, progress bar)
- Last 14 entries table: date, weight, sleep
- Manage panel: Edit details / Deactivate / Remove from dashboard (with confirm)

#### `/client/<name>/nutrition` → `cronometer_nutrition.html`
**This is the "show everything" page — do not water anything down.**

Per-day view (selected from calendar):
- **Macros**: calories, protein, carbs, fat, fiber — each as a bar vs target
  with a numeric total + target + remaining
- **Per-food expandable detail**: for each food logged that day, show all
  available nutrients (not just the headline macros). The data comes from
  `cronometer_client.structure_servings` which provides `details` (a dict of
  every micronutrient). Surface all of it — vitamins, minerals, omega-3,
  cholesterol, sodium, etc. — in an expandable section per food.
- **Daily totals vs targets** with progress bars for every tracked nutrient
- **Month calendar** with data dots on days that have logged data
- **30-day calorie trend** (Plotly line chart)

#### `/client/<name>/cronometer` → `client_cronometer.html`
- Credentials panel (save/update Cronometer email + password)
- View foods & nutrients link
- Sync calories to sheet form (number of days)
- Remove stored credentials button

#### `/cronometer/foods` → `cronometer_foods.html`
- Per-food log: food name, serving, calories, macros
- Each food expandable to show full nutrient breakdown

#### `/client/<name>/log` → `client_log.html`
- 3 forms side-by-side: Log weight (date + weight), Log sleep (date + hours),
  Mark payment received (date)
- All date inputs use flatpickr dd/mm/yyyy

#### `/clients/new` → `client_new.html`
- 6-step wizard with stepper UI
- Step 1: Client info (name, email, program name, goal, start date, unit,
  plan, billing day)
- Step 2: Program — dynamic session list (add/remove/reorder sessions with
  custom labels) + exercise table (session, exercise, sets, reps, notes,
  tutorial URL) + preset loader
- Step 3: Week & RIR (number of weeks, RIR per week)
- Step 4: Nutrition & sleep targets (calories, protein, carbs, fat, fiber,
  sleep target)
- Step 5: Review (summary of all entered data)
- Step 6: Generate button (one-click → sheet generated + client registered)

#### `/clients/add` → `client_add.html`
- Two paths: connect an existing sheet (form) OR start guided setup (link)

#### `/client/<name>/edit` → `client_edit.html`
- Edit name, sheet URL/ID, plan, weight unit
- Advanced: master sheet ID override

#### `/library` → `library.html`
- List of saved programs (name, days/week, exercise count, last updated)
- Edit + Delete per program

#### `/library/<id>/edit` → `library_edit.html`
- Program name + notes
- Dynamic session list (add/remove/reorder) with session label inputs
- Exercise table (session, exercise, sets, reps, notes, tutorial URL)
- Session labels populate the `ex_type` datalist dynamically

#### `/guide` → `guide.html`
- Setup/help documentation for the coach

#### `/login` → `login.html`
- Single passcode field + submit

---

## Technical notes for the redesign

- All Jinja2 template syntax (`{{ }}`, `{% %}`) must be preserved exactly.
- The `csrf_input()` call in every POST form is a security requirement — do not
  remove it.
- CSS variables (custom properties) in `style.css` drive the colour scheme —
  prefer extending them rather than hardcoding hex values in templates.
- The `session-labels` and `session-type-list` datalists in the wizard and
  library editor are dynamically updated by JavaScript — keep the element IDs.
- Plotly chart containers must keep their `id` attributes (`chart-weight`,
  `chart-calories`, etc.) — the JS in `{% block scripts %}` references them.
- flatpickr is initialised globally in `base.html` on `.js-date` class — keep
  that class on all date inputs.
