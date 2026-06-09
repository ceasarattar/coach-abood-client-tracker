"""
Glue between Cronometer and the client Google Sheet.

Writes each day's calories into the client sheet's Weight tab (col J, "Calories",
dated by col A) — the exact path the dashboard's calorie chart already reads
(`Weight!J`, see sheets_client.WEIGHT_CALORIES_RANGE). Only rows whose date
already exists in the Weight tab are updated; unmatched dates are skipped.

The Weight tab is a *fixed dated grid* (140 rows from the program start date), so
Cronometer days that fall outside that range have nowhere to go. To make the sync
actually fill the recent days, the caller aligns the Cronometer pull window to the
dates the sheet covers (see `days_to_cover`), and the result reports the sheet's
date range so a "nothing matched" outcome is self-explanatory.
"""
import datetime as _dt
from datetime import date, timedelta

import sheets_client as sc

# Day-first first (the app/sheet convention), then other common shapes.
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
                 "%d-%m-%Y", "%b %d, %Y", "%B %d, %Y")


def _parse_one(raw):
    """Parse a single Weight!A date cell to a date, or None. Tolerant of a
    leading weekday (e.g. 'Sat 07/06/2026') and stray whitespace."""
    s = str(raw or "").strip()
    if not s:
        return None
    parts = s.split()
    if len(parts) == 2 and ("/" in parts[1] or "-" in parts[1]):
        s = parts[1]            # drop a leading weekday name
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def weight_date_rows(service, spreadsheet_id: str) -> dict:
    """Map ISO date string -> 1-based Weight-tab row (col A holds the dates)."""
    data = sc.fetch_ranges(service, spreadsheet_id, ["Weight!A2:A"])
    col = data.get("Weight!A2:A", [])
    mapping = {}
    for i, cell in enumerate(col):
        d = _parse_one(cell[0] if cell else "")
        if d:
            mapping[d.isoformat()] = i + 2  # A2 is row 2
    return mapping


def days_to_cover(date_rows: dict, user_days: int = 14, cap: int = 90) -> int:
    """
    How many days back to pull from Cronometer so the window reaches the earliest
    sheet date that is on/before today — capped at `cap`, and never less than the
    user's requested `user_days`. This is what makes recent logged days actually
    line up with the fixed dated grid in the Weight tab.
    """
    today = date.today()
    past = [date.fromisoformat(d) for d in date_rows
            if date.fromisoformat(d) <= today]
    if not past:
        return user_days
    earliest = max(min(past), today - timedelta(days=cap))
    return max(user_days, (today - earliest).days + 1)


def sheet_range_str(date_rows: dict) -> str:
    """Human 'dd/mm/yyyy–dd/mm/yyyy' span of the Weight tab's dates, or ''."""
    if not date_rows:
        return ""
    ds = sorted(date.fromisoformat(d) for d in date_rows)
    return f"{ds[0].strftime('%d/%m/%Y')}–{ds[-1].strftime('%d/%m/%Y')}"


def sync_to_sheet(service, spreadsheet_id: str, rows: list,
                  date_rows: dict = None) -> dict:
    """
    Write calories from `rows` (cronometer daily output) into Weight!J, matched by
    date. Returns {'written', 'skipped', 'dates', 'range_str'}.
    Pass `date_rows` (from weight_date_rows) to avoid a second read.
    """
    if date_rows is None:
        date_rows = weight_date_rows(service, spreadsheet_id)

    updates = []
    written_dates = []
    skipped = 0
    for r in rows:
        iso = r.get("date")
        cals = r.get("calories")
        row = date_rows.get(iso)
        if row is None or cals is None:
            skipped += 1
            continue
        updates.append({"range": f"Weight!J{row}", "values": [[cals]]})
        written_dates.append(iso)

    if updates:
        sc.batch_update_values(service, spreadsheet_id, updates)

    return {"written": len(updates), "skipped": skipped,
            "dates": written_dates, "range_str": sheet_range_str(date_rows)}
