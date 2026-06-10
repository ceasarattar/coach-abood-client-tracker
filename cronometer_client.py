"""
Cronometer nutrition fetcher.

Cronometer has no public API, so this drives Cronometer's own **CSV export** with
a headless browser (Playwright) and parses the result. The CSV parsing is a pure
function (`parse_daily_nutrition_csv`) and is unit-tested; the browser steps are
isolated below and centralised so selectors live in ONE place.

>>> IMPORTANT <<<
The login/export selectors and URLs below are best-effort and must be validated
once against a real Cronometer account (the UI changes over time). Everything
that can break lives in the CONFIG block — adjust there, nowhere else.

Returns a list of daily rows:
    [{"date": "YYYY-MM-DD", "calories": float|None, "protein": ..., "carbs": ...,
      "fat": ..., "fiber": ...}, ...]
"""
import csv
import io
import logging
import datetime as _dt

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# CONFIG — the only place selectors / URLs should need editing.
# --------------------------------------------------------------------------
LOGIN_URL = "https://cronometer.com/login/"
EXPORT_URL = "https://cronometer.com/exports/"  # validate: account export page

SEL_EMAIL = "input[name='username'], input[type='email'], #username"
SEL_PASSWORD = "input[name='password'], input[type='password'], #password"
SEL_LOGIN_BTN = "button[type='submit'], #login-button, button:has-text('Login')"
# Element only present once logged in (used to confirm auth succeeded):
SEL_LOGGED_IN = "text=Diary, .app, #diary"

NAV_TIMEOUT_MS = 30000


# --------------------------------------------------------------------------
# Pure CSV parsing (unit-tested — no browser needed)
# --------------------------------------------------------------------------
def _match_col(headers, *needles):
    """Return the header whose lowercased text contains all needles, or None."""
    for h in headers:
        hl = h.lower()
        if all(n in hl for n in needles):
            return h
    return None


def _energy_col(headers):
    """
    Find the *total* daily energy column.

    Cronometer's CSV can contain multiple energy-related columns:
    "Energy (kcal)", "Energy from Fat (kcal)", "Calories from Fat", etc.
    A naive `_match_col(headers, "energy", "kcal")` returns the first match,
    which may be a per-macro derived column rather than the daily total.

    Strategy (first wins):
      1. Case-insensitive exact match against known total-energy names.
      2. Shortest column whose lowercase name *starts with* "energy" or "calorie"
         (avoids "Energy from Fat" which starts with "energy from").
      3. Fall back to original broad search.
    """
    # 1. Known exact names Cronometer uses for the daily total
    _EXACT = ("energy (kcal)", "energy (cal)", "calories", "total calories",
              "energy", "kcal")
    hl_map = {h.lower().strip(): h for h in headers}
    for name in _EXACT:
        if name in hl_map:
            return hl_map[name]

    # 2. Shortest column starting with "energy" or "calorie/calories"
    candidates = [h for h in headers
                  if h.lower().strip().startswith(("energy", "calorie"))]
    if candidates:
        return min(candidates, key=len)   # "Energy (kcal)" shorter than "Energy from Fat (kcal)"

    # 3. Broad fallback (original behaviour)
    return (_match_col(headers, "energy", "kcal")
            or _match_col(headers, "calorie")
            or _match_col(headers, "energy"))


def _to_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _norm_date(val):
    """Normalise a Cronometer date cell to ISO YYYY-MM-DD, or None."""
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return _dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_daily_nutrition_csv(text: str) -> list:
    """
    Parse a Cronometer 'Daily Nutrition' style CSV into normalised daily rows.

    Columns are matched by name using _energy_col() for the total energy column
    (avoids picking "Energy from Fat (kcal)" over "Energy (kcal)").

    Multiple rows for the same date are summed — Cronometer can emit one row per
    meal group (Breakfast / Lunch / Dinner / Snacks / Uncategorized) for the same
    day, in which case naively taking the last row would silently under-report.
    """
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        return []

    c_date = _match_col(headers, "date")
    c_cals = _energy_col(headers)
    c_prot = _match_col(headers, "protein")
    c_carb = _match_col(headers, "carb")
    # Prefer a plain "Fat (g)" over "Saturated Fat (g)" etc.
    c_fat = (next((h for h in headers if h.lower().strip().startswith("fat")), None)
             or _match_col(headers, "fat"))
    c_fiber = _match_col(headers, "fiber") or _match_col(headers, "fibre")

    logger.debug("parse_daily_nutrition_csv columns: date=%s cals=%s prot=%s carb=%s fat=%s fiber=%s",
                 c_date, c_cals, c_prot, c_carb, c_fat, c_fiber)

    # Accumulate per date — handles both 1-row-per-day and meal-group formats.
    totals: dict = {}   # iso -> {date, calories, protein, carbs, fat, fiber}
    order: list = []

    for row in reader:
        iso = _norm_date(row.get(c_date, "")) if c_date else None
        if not iso:
            continue
        if iso not in totals:
            totals[iso] = {"date": iso,
                           "calories": None, "protein": None,
                           "carbs": None, "fat": None, "fiber": None}
            order.append(iso)
        entry = totals[iso]
        for field, col in (("calories", c_cals), ("protein", c_prot),
                           ("carbs", c_carb), ("fat", c_fat), ("fiber", c_fiber)):
            v = _to_float(row.get(col)) if col else None
            if v is not None:
                entry[field] = (entry[field] or 0.0) + v

    return list(totals[iso] for iso in order)


def parse_servings_csv(text: str) -> dict:
    """
    Parse a Cronometer 'Servings' export — one row per food logged, with every
    nutrient column Cronometer provides — into a passthrough structure:

        {'headers': [<all columns, in order>],
         'date_col': <the day/date column header, or None>,
         'rows':   [ {col: value, ...}, ... ]   # newest day first}

    Generic on purpose: every column is preserved so the dashboard can show
    "everything you see in Cronometer" — foods, amounts, macros and micros.
    """
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    if not headers:
        return {"headers": [], "date_col": None, "rows": []}

    date_col = _match_col(headers, "day") or _match_col(headers, "date")
    rows = [{h: (row.get(h, "") or "") for h in headers} for row in reader]
    if date_col:
        rows.sort(key=lambda r: _norm_date(r.get(date_col, "")) or "", reverse=True)
    return {"headers": headers, "date_col": date_col, "rows": rows}


def _fat_col(headers):
    """The plain 'Fat (g)' column, not 'Saturated Fat (g)' etc."""
    return (next((h for h in headers if h.lower().strip().startswith("fat")), None)
            or _match_col(headers, "fat"))


def structure_servings(parsed: dict) -> dict:
    """
    Shape parse_servings_csv() output into a Cronometer-style, per-day view:

        {'days': [ {'date': 'dd/mm/yyyy',
                    'totals': {'energy','protein','carbs','fat'},
                    'foods': [ {'name','amount','energy','protein','carbs','fat',
                                'details': [(nutrient, value), ...]} ] } ],
         'count': <total food rows>}

    Headline macros (food, amount, energy, protein, carbs, fat) are pulled out for
    the summary row; every other non-empty nutrient column becomes an expandable
    detail. Days come newest-first (parse_servings_csv already sorts the rows).
    """
    headers = parsed.get("headers", [])
    rows = parsed.get("rows", [])
    day_col = parsed.get("date_col")

    food_col = _match_col(headers, "food", "name") or _match_col(headers, "food")
    amount_col = _match_col(headers, "amount") or _match_col(headers, "quantity")
    energy_col = (_match_col(headers, "energy", "kcal")
                  or _match_col(headers, "energy") or _match_col(headers, "calorie"))
    protein_col = _match_col(headers, "protein")
    carbs_col = _match_col(headers, "carb")
    fat_col = _fat_col(headers)

    headline = {c for c in (day_col, food_col, amount_col, energy_col,
                            protein_col, carbs_col, fat_col) if c}
    detail_cols = [h for h in headers if h not in headline]

    def fmt_date(raw):
        iso = _norm_date(raw)
        if not iso:
            return str(raw or "").strip()
        y, m, d = iso.split("-")
        return f"{d}/{m}/{y}"

    days, order = {}, []
    for r in rows:
        key = (r.get(day_col, "") or "").strip() if day_col else ""
        if key not in days:
            days[key] = {"date": fmt_date(key),
                         "totals": {"energy": 0.0, "protein": 0.0,
                                    "carbs": 0.0, "fat": 0.0},
                         "foods": []}
            order.append(key)
        food = {
            "name": (r.get(food_col, "") if food_col else "").strip() or "—",
            "amount": (r.get(amount_col, "") if amount_col else "").strip(),
            "energy": (r.get(energy_col, "") if energy_col else "").strip(),
            "protein": (r.get(protein_col, "") if protein_col else "").strip(),
            "carbs": (r.get(carbs_col, "") if carbs_col else "").strip(),
            "fat": (r.get(fat_col, "") if fat_col else "").strip(),
            "details": [(c, str(r.get(c, "")).strip()) for c in detail_cols
                        if str(r.get(c, "")).strip() not in ("", "0")],
        }
        days[key]["foods"].append(food)
        for k, col in (("energy", energy_col), ("protein", protein_col),
                       ("carbs", carbs_col), ("fat", fat_col)):
            v = _to_float(r.get(col)) if col else None
            if v:
                days[key]["totals"][k] += v

    out_days = []
    for key in order:
        day = days[key]
        day["totals"] = {k: round(v, 1) for k, v in day["totals"].items()}
        out_days.append(day)
    return {"days": out_days, "count": len(rows)}


# --------------------------------------------------------------------------
# Browser-driven fetch (Playwright) — needs validation with a real account
# --------------------------------------------------------------------------
def fetch_daily_nutrition(email: str, password: str, days: int = 14,
                          headless: bool = True) -> list:
    """
    Log into Cronometer, export the last `days` of daily nutrition as CSV, and
    return parsed rows. Raises RuntimeError with a readable message on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run:  pip install playwright  and then "
            "python -m playwright install chromium"
        ) from exc

    end = _dt.date.today()
    start = end - _dt.timedelta(days=days)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        try:
            page.goto(LOGIN_URL, timeout=NAV_TIMEOUT_MS)
            page.fill(SEL_EMAIL, email)
            page.fill(SEL_PASSWORD, password)
            page.click(SEL_LOGIN_BTN)
            page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)

            # Trigger the official CSV export and capture the download.
            # (Validate this against the live export UI — see CONFIG above.)
            page.goto(EXPORT_URL, timeout=NAV_TIMEOUT_MS)
            with page.expect_download(timeout=NAV_TIMEOUT_MS) as dl_info:
                _trigger_daily_export(page, start, end)
            download = dl_info.value
            csv_text = _read_download(download)
        except Exception as exc:  # noqa: BLE001 — surface a clean message
            raise RuntimeError(f"Cronometer fetch failed: {exc}") from exc
        finally:
            ctx.close()
            browser.close()

    rows = parse_daily_nutrition_csv(csv_text)
    if not rows:
        raise RuntimeError("Logged in, but the export returned no parseable rows "
                           "— the export format may have changed.")
    return rows


def _trigger_daily_export(page, start, end):
    """
    Click through Cronometer's export to download a 'Daily Nutrition' CSV for the
    date range. ISOLATED so it's the single place to fix when the UI changes.
    """
    # Best-effort: many Cronometer exports expose a direct link. If your account
    # uses the date-range dialog instead, replace this body with the click steps.
    page.get_by_text("Daily Nutrition", exact=False).first.click()


def _read_download(download) -> str:
    path = download.path()
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()
