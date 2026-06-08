# Coach Abood Dashboard — design → code handoff

This is a **clickable design prototype** of the dashboard, built in React (in-browser
Babel, no build step). It mirrors the real Flask app's routes, data shapes, and the
seed program data — so you can lift the visual design into the Jinja templates without
re-deriving anything.

**It is a design reference, not the running app.** No Google Sheets calls, no SQLite —
all data is local fixtures generated to look real. Wiring is `app/`-relative.

---

## How to give this to Claude Code

Paste this whole folder (or just the `app/` folder + `Coach Dashboard.html`) into the
repo and tell Claude Code:

> Reskin the Flask templates to match `Coach Dashboard.html`. Keep all routes, form
> field names, and template variables exactly as they are in `app.py` / the current
> templates — only change the markup + CSS. The prototype's `app/styles.css` is the
> source of truth for the design system.

The prototype deliberately keeps the **same field names and route semantics** as the
Flask app, so the mapping is mechanical.

---

## Page ↔ template ↔ route map

| Prototype (file · component) | Flask route | Jinja template | Notes |
|---|---|---|---|
| `pages-clients.jsx` · `ClientsPage` | `GET /` | `index.html` | Card grid. Cards read the same fields `build_card()` returns. |
| `pages-clients.jsx` · `ClientDetailPage` | `GET /client/<name>` | `client.html` | Stat strip + weight chart + calorie chart + week-summary table + weight table + payment table. |
| `pages-clients.jsx` · `LogModal` | `GET/POST /client/<name>/log` | `client_log.html` | Same two actions (`kind=weight`, `kind=payment`) — rendered as a modal instead of a separate page. Hidden fields map 1:1. |
| `pages-library.jsx` · `LibraryPage` | `GET /library` (+ `POST /library/<id>/delete`) | `library.html` | Program list. Day-chips visualise `program.schedule`. |
| `pages-library.jsx` · `ProgramEditorPage` | `GET/POST /library/new` · `/library/<id>/edit` | `library_edit.html` | Schedule inputs (`schedule_<Day>`) + exercise rows (`ex_type/ex_name/ex_sets/ex_reps/ex_notes/ex_url`). |
| `pages-add.jsx` · `AddClientPage` | `GET/POST /clients/add` | `client_add.html` | The "Connect an existing sheet" card = the current add form (`name`, `sheet`, `plan`, `weight_unit`, `master_sheet`). |
| `pages-add.jsx` · `NewClientWizard` | `GET/POST /clients/new` | `client_new.html` | 6-step wizard. `write_master` then `register` actions unchanged. |

### One deliberate UX change
The old app had **two** add entry points (`/clients/add` and `/clients/new`). The
prototype unifies them into a single **Add client** page that offers both paths
(connect existing · build from scratch). Keep both routes in Flask — just point the
nav at `/clients/add` and link "Start guided setup" → `/clients/new`. The duplicate
nav button is gone.

---

## Data shapes (already match `app.py`)

- **Card** — `build_card()`: `name, plan_usd, weight_unit, status, latest_weight,
  weight_delta, spark, last_logged{date,days_ago}, payment_display, payment_class`.
- **Detail** — `build_detail()`: adds `weight30[{d,v,ma7}]`, `cal30[{d,v}]`,
  `week_summary[{week,logged,total}]`, `weight_table[{date,val}]`, `payment_record`.
- **Program** — matches `db.get_program()`: `{id,name,notes,schedule[],exercises[]}`.
  The real seed (`seed/programs.json`) is embedded verbatim in `app/data/programs.js`.
- **Payment columns** — `window.PAYMENT_COLUMNS` is the exact `PAYMENT_COLUMNS` list.

In the prototype these come from `app/data/clients.js` (generated) and
`app/data/programs.js` (your real seed). In Flask they come from the Sheets API —
the template bindings are identical, so only the markup changes.

---

## Design system (`app/styles.css`)

- **Theme** — calm dark, cool-neutral ink surfaces, one accent + traffic-light status.
- **Type** — `Hanken Grotesk` (UI) + `IBM Plex Mono` (data, IDs, dates, technical hints).
- **Tokens** — all colors are CSS custom properties under `:root` (oklch). Accent is
  themeable (the Tweaks panel swaps `--accent`); density via `[data-density]`.
- **Components** — `.panel`, `.btn(.btn-primary/.btn-ghost/.btn-danger)`, `.badge`,
  `.dot`, `.table`, `.input/.select`, `.seg`, `.pill`, `.toast`, `.ph` (placeholder).
- **Charts** — hand-built inline SVG (`components.jsx`: `WeightChart`, `CalorieChart`,
  `Sparkline`). The real app currently uses Plotly; you can either keep Plotly and
  restyle it to these colors, or port these SVG renderers. Colors to feed Plotly:
  weight line `var(--accent)`, 7-day avg `var(--amber)`, calorie target `var(--green)`.

## File layout
```
Coach Dashboard.html      entry — loads fonts, styles, React/Babel, then app/*
app/styles.css            design system (tokens + components)
app/components.jsx        Icon, StatusDot, Badge, charts, toast
app/pages-clients.jsx     Clients grid · Client detail · Log modal
app/pages-library.jsx     Library list · Program editor
app/pages-add.jsx         Add client (unified) · New-client wizard
app/main.jsx              shell, sidebar, hash router, tweaks
app/data/programs.js      real seed programs (from seed/programs.json)
app/data/clients.js       generated client fixtures
app/tweaks-panel.jsx      tweaks shell (design-tool only — drop on port to prod)
```
