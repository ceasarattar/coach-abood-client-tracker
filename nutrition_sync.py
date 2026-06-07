"""
Glue between Cronometer and the client Google Sheet.

Writes each day's calories into the client sheet's Weight tab (col J, "Calories",
dated by col A) — the exact path the dashboard's calorie chart already reads
(`Weight!J`, see sheets_client.WEIGHT_CALORIES_RANGE). Only rows whose date
already exists in the Weight tab are updated; unmatched dates are skipped.

Kept separate from cronometer_client (the fetch) so the brittle browser code and
the safe sheet-write code can be tested and changed independently.
"""
import datetime as _dt

import sheets_client as sc


def _weight_date_rows(service, spreadsheet_id: str) -> dict:
    """Map ISO date string -> 1-based Weight-tab row (col A holds the dates)."""
    data = sc.fetch_ranges(service, spreadsheet_id, ["Weight!A2:A"])
    col = data.get("Weight!A2:A", [])
    mapping = {}
    for i, cell in enumerate(col):
        raw = (cell[0] if cell else "").strip()
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                iso = _dt.datetime.strptime(raw, fmt).date().isoformat()
                mapping[iso] = i + 2  # A2 is row 2
                break
            except ValueError:
                pass
    return mapping


def sync_to_sheet(service, spreadsheet_id: str, rows: list) -> dict:
    """
    Write calories from `rows` (cronometer_client output) into Weight!J.
    Returns {'written': n, 'skipped': m, 'dates': [iso, ...]}.
    """
    date_rows = _weight_date_rows(service, spreadsheet_id)
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

    return {"written": len(updates), "skipped": skipped, "dates": written_dates}
