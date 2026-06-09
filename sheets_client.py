"""
Google Sheets API client for the Coach Abood dashboard.

Handles OAuth (read + write), batched reads (batchGet) with graceful fallback
when a named range is missing, batched writes (values batchUpdate), and tab
listing.

Hard rules (project Section 6):
  * Never reference a sheet by getSheetById — always by name string.
  * All reads go through batchGet; all writes through values batchUpdate.
  * OAuth scope is read + write: spreadsheets (NOT spreadsheets.readonly).
"""
import os
import json
import time
import logging

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Read + write scope (upgraded from spreadsheets.readonly).
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Service-account key: provided inline via an env var (production / Render) or
# as a local file next to this module (dev). Resolved relative to this file so
# the launch CWD does not matter.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_ENV = 'GOOGLE_SERVICE_ACCOUNT_JSON'
SERVICE_ACCOUNT_FILE = os.path.join(_BASE_DIR, 'service_account.json')
# Legacy paths — kept only so stray references don't break; no longer used.
TOKEN_PATH = os.path.join(_BASE_DIR, 'token.json')
CREDS_PATH = os.path.join(_BASE_DIR, 'credentials.json')

# Named ranges that exist in a generated client sheet (verified against the
# real workbook). WorkoutDates / WorkoutCompletion / WorkoutVolume were removed
# (the workout layout is now per-week tabs read directly by name). CalorieTarget
# and Payment_Status_Range never existed as named ranges.
CLIENT_NAMED_RANGES = [
    'WeightDates',          # Weight!A2:A
    'WeightValues',         # Weight!B2:B
    'WeightMA7',            # Weight!D2:D  (running avg, used as MA proxy)
    'WeeklyAvg',            # Weight!E2:E
    'DailyTotal_Calories',  # Nutrition!B34 (single cell — today's total)
]

# A1 fallback for each named range, used if the named range 404s on the live
# sheet (e.g. an older sheet generated before the range was added).
NAMED_RANGE_A1_FALLBACK = {
    'WeightDates': 'Weight!A2:A',
    'WeightValues': 'Weight!B2:B',
    'WeightMA7': 'Weight!D2:D',
    'WeeklyAvg': 'Weight!E2:E',
    'DailyTotal_Calories': 'Nutrition!B34',
}

# Dated daily-calorie history lives on the Weight tab (col J = Calories,
# dates in col A). This is the data path a future Cronometer importer will
# populate. Read by A1 (no named range).
WEIGHT_CALORIES_RANGE = 'Weight!J2:J'

# Master sheet Payments tab. Header is on row 2, data from row 3. No named
# range exists on the master sheet, so this is read by A1.
PAYMENTS_RANGE = 'Payments!A3:I'


class ReauthRequired(Exception):
    """Kept for backward-compatibility. Service accounts never need re-auth."""
    pass


class SheetsNotConfigured(FileNotFoundError):
    """Raised when no service-account key is available (env var or file).

    Subclasses FileNotFoundError so existing `except FileNotFoundError`
    handlers keep showing the setup page.
    """
    pass


def _service_account_info():
    """Return the service-account dict from the env var or local file, or None."""
    raw = os.environ.get(SERVICE_ACCOUNT_ENV, '').strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SheetsNotConfigured(
                f'{SERVICE_ACCOUNT_ENV} is set but is not valid JSON: {exc}') from exc
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        with open(SERVICE_ACCOUNT_FILE, encoding='utf-8') as fh:
            return json.load(fh)
    return None


def sheets_configured() -> bool:
    """True if a service-account key is available (so Sheets calls can run)."""
    try:
        return _service_account_info() is not None
    except SheetsNotConfigured:
        return False


def service_account_email() -> str:
    """The service account's email (to share sheets with), or '' if unconfigured."""
    try:
        info = _service_account_info()
    except SheetsNotConfigured:
        info = None
    return (info or {}).get('client_email', '')


# Cache the built service so the key is not reparsed on every request.
_service_cache = None


def authenticate(force: bool = False):
    """Return an authorized Sheets service backed by the service account.

    Raises SheetsNotConfigured (a FileNotFoundError subclass) when no key is
    available, so callers' existing FileNotFoundError handling still works.
    """
    global _service_cache
    if _service_cache is not None and not force:
        return _service_cache
    info = _service_account_info()
    if info is None:
        raise SheetsNotConfigured(
            'No Google service-account key found. Set the '
            f'{SERVICE_ACCOUNT_ENV} env var or add service_account.json '
            '(see DEPLOY.md).')
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    _service_cache = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    return _service_cache


def _batch_get(service, spreadsheet_id: str, ranges: list) -> dict:
    """Single batchGet with 429 exponential backoff. Returns the raw response."""
    max_retries = 3
    delay = 1
    for attempt in range(max_retries):
        try:
            return (
                service.spreadsheets()
                .values()
                .batchGet(spreadsheetId=spreadsheet_id, ranges=ranges)
                .execute()
            )
        except HttpError as exc:
            if exc.resp.status == 429 and attempt < max_retries - 1:
                logger.warning(
                    'Rate limited (429) for %s — retrying in %ds (%d/%d)',
                    spreadsheet_id, delay, attempt + 1, max_retries,
                )
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError('_batch_get: unreachable')


def fetch_client_data(service, spreadsheet_id: str) -> dict:
    """
    Fetch all client data needed by the dashboard in as few calls as possible.

    Returns a dict keyed by logical name -> value matrix (list of rows):
        WeightDates, WeightValues, WeightMA7, WeeklyAvg, DailyTotal_Calories,
        WeightCalories
    Missing named ranges degrade gracefully via an A1 fallback so one absent
    range cannot blank out the whole page.
    """
    ranges = list(CLIENT_NAMED_RANGES) + [WEIGHT_CALORIES_RANGE]
    try:
        raw = _batch_get(service, spreadsheet_id, ranges)
        vrs = raw.get('valueRanges', [])
        data = {
            name: vrs[i].get('values', []) if i < len(vrs) else []
            for i, name in enumerate(CLIENT_NAMED_RANGES)
        }
        idx = len(CLIENT_NAMED_RANGES)
        data['WeightCalories'] = vrs[idx].get('values', []) if idx < len(vrs) else []
        return data
    except HttpError as exc:
        logger.warning(
            'batchGet failed for %s (%s); retrying ranges individually',
            spreadsheet_id, exc,
        )
        return _fetch_client_data_individually(service, spreadsheet_id)


def _fetch_client_data_individually(service, spreadsheet_id: str) -> dict:
    """Fallback path: fetch each range alone, swapping in A1 if a name 404s."""
    data: dict = {}
    for name in CLIENT_NAMED_RANGES:
        data[name] = _safe_get(service, spreadsheet_id, name,
                               NAMED_RANGE_A1_FALLBACK.get(name))
    data['WeightCalories'] = _safe_get(
        service, spreadsheet_id, WEIGHT_CALORIES_RANGE, None
    )
    return data


def _safe_get(service, spreadsheet_id: str, primary: str, fallback) -> list:
    """Get one range; if it fails and a fallback A1 is given, try that."""
    for rng in (primary, fallback):
        if not rng:
            continue
        try:
            res = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=rng)
                .execute()
            )
            return res.get('values', [])
        except HttpError as exc:
            logger.warning("Range '%s' unavailable in %s: %s",
                          rng, spreadsheet_id, exc)
    return []


def fetch_payments(service, master_spreadsheet_id: str) -> list:
    """
    Read the master sheet's Payments tab (rows from row 3) via batchGet.
    Returns a list of rows (each a list of cell strings). Empty on failure.
    """
    if not master_spreadsheet_id:
        return []
    try:
        raw = _batch_get(service, master_spreadsheet_id, [PAYMENTS_RANGE])
        vrs = raw.get('valueRanges', [])
        return vrs[0].get('values', []) if vrs else []
    except HttpError as exc:
        logger.error('Payments read failed for %s: %s',
                     master_spreadsheet_id, exc)
        return []


def get_sheet_tab_names(service, spreadsheet_id: str) -> list:
    """Return the list of tab (sheet) title strings — never by id."""
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields='sheets.properties.title')
        .execute()
    )
    return [s['properties']['title'] for s in meta.get('sheets', [])]


def fetch_ranges(service, spreadsheet_id: str, ranges: list) -> dict:
    """
    Generic batchGet of arbitrary A1/named ranges.
    Returns {range_string: value_matrix}.
    """
    raw = _batch_get(service, spreadsheet_id, ranges)
    vrs = raw.get('valueRanges', [])
    return {
        ranges[i]: (vrs[i].get('values', []) if i < len(vrs) else [])
        for i in range(len(ranges))
    }


def batch_update_values(service, spreadsheet_id: str, updates: list,
                        value_input_option: str = 'USER_ENTERED') -> dict:
    """
    Write multiple ranges in a single values batchUpdate.

    `updates` is a list of {'range': '<A1 or named>', 'values': [[...], ...]}.
    USER_ENTERED makes Sheets parse dates/numbers the way a human entry would.
    """
    body = {'valueInputOption': value_input_option, 'data': updates}
    return (
        service.spreadsheets()
        .values()
        .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
        .execute()
    )
