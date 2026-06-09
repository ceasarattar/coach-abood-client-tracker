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
import datetime as _dt

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
    Columns are matched by name (order-independent), so minor export changes
    don't break it.
    """
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        return []

    c_date = _match_col(headers, "date")
    c_cals = (_match_col(headers, "energy", "kcal") or _match_col(headers, "calorie")
              or _match_col(headers, "energy"))
    c_prot = _match_col(headers, "protein")
    c_carb = _match_col(headers, "carb")
    # Prefer a plain "Fat (g)" over "Saturated Fat (g)" etc.
    c_fat = (next((h for h in headers if h.lower().strip().startswith("fat")), None)
             or _match_col(headers, "fat"))
    c_fiber = _match_col(headers, "fiber") or _match_col(headers, "fibre")

    out = []
    for row in reader:
        iso = _norm_date(row.get(c_date, "")) if c_date else None
        if not iso:
            continue
        out.append({
            "date": iso,
            "calories": _to_float(row.get(c_cals)) if c_cals else None,
            "protein": _to_float(row.get(c_prot)) if c_prot else None,
            "carbs": _to_float(row.get(c_carb)) if c_carb else None,
            "fat": _to_float(row.get(c_fat)) if c_fat else None,
            "fiber": _to_float(row.get(c_fiber)) if c_fiber else None,
        })
    return out


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
