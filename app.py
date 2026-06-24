import os
import re
import json
import secrets
import logging
import logging.handlers
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib.parse import unquote, urlparse

from flask import (Flask, render_template, redirect, url_for, jsonify, abort,
                   request, flash, session)
from markupsafe import Markup
from googleapiclient.errors import HttpError

import sheets_client as sc
import db
import cache
import secrets_store
import cronometer_api
import cronometer_client
import nutrition_sync

# ---------------------------------------------------------------------------
# Paths + config + app + logging
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENTS_FILE = os.path.join(BASE_DIR, 'clients.yaml')   # legacy — imported on first boot
ENV_FILE = os.path.join(BASE_DIR, '.env')


def _load_dotenv_into_environ() -> None:
    """Load .env into os.environ for local dev. Does NOT override variables that
    are already set, so a hosting platform's real env vars always win."""
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv_into_environ()

app = Flask(__name__)
app.secret_key = (os.environ.get('SECRET_KEY')
                  or os.environ.get('FLASK_SECRET')
                  or 'coach-khader-local-dev-secret')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Shared passcode that gates the whole app once it is hosted publicly.
# If unset (local dev), the gate is disabled so nothing blocks development.
APP_PASSCODE = os.environ.get('APP_PASSCODE', '').strip()

# Create tables, seed the workout library, and import any legacy clients.yaml.
# Safe to run on every process start (each step is guarded).
try:
    db.bootstrap()
except Exception:
    logging.getLogger(__name__).exception('db.bootstrap() failed at startup')

os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
_fh = logging.handlers.RotatingFileHandler(
    os.path.join(BASE_DIR, 'logs', 'dashboard.log'),
    maxBytes=5 * 1024 * 1024, backupCount=3,
)
_fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_fh])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Access gate — a shared passcode protects the app once it is public (Render).
# Disabled automatically when APP_PASSCODE is unset (local development).
# ---------------------------------------------------------------------------

_PUBLIC_ENDPOINTS = {'login', 'logout', 'health', 'static', 'service_worker', 'reauth'}


def _csrf_token() -> str:
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def _csrf_input() -> Markup:
    return Markup(f'<input type="hidden" name="csrf_token" value="{_csrf_token()}">')


@app.context_processor
def _inject_globals():
    """Expose whether the passcode gate is active (controls Sign-out link) + CSRF helper."""
    return {'app_gated': bool(APP_PASSCODE),
            'csrf_input': _csrf_input,
            'csrf_token': _csrf_token}


@app.before_request
def _require_login():
    if not APP_PASSCODE:
        return  # gate disabled (local dev)
    if request.endpoint in _PUBLIC_ENDPOINTS or session.get('authed'):
        return
    return redirect(url_for('login', next=request.path))


@app.before_request
def _check_csrf():
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return
    if request.endpoint in _PUBLIC_ENDPOINTS:
        return
    # Allow requests from the service worker / health endpoint
    if request.endpoint in ('health',):
        return
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token', '')
    if not token or token != session.get('csrf_token'):
        abort(403)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not APP_PASSCODE or session.get('authed'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        if (request.form.get('passcode') or '').strip() == APP_PASSCODE:
            session['authed'] = True
            session.permanent = True
            return redirect(request.args.get('next') or url_for('index'))
        flash('Incorrect passcode.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))




# ---------------------------------------------------------------------------
# Global error handlers — never leak a traceback to the user; always render a
# branded page. 500s are logged with full context for the dashboard.log.
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def _not_found(err):
    return render_template('404.html'), 404


@app.errorhandler(500)
@app.errorhandler(Exception)
def _server_error(err):
    # HTTP errors (abort(4xx)) keep their own status; everything else is a 500.
    from werkzeug.exceptions import HTTPException
    if isinstance(err, HTTPException):
        if err.code == 404:
            return render_template('404.html'), 404
        return render_template('500.html', code=err.code,
                               message=err.description), err.code
    logger.error('Unhandled exception on %s', request.path, exc_info=True)
    return render_template('500.html', code=500, message=None), 500


@app.route('/sw.js')
def service_worker():
    """Serve the service worker from the site root so its scope is the whole app."""
    resp = app.send_static_file('sw.js')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


# Master Payments tab columns (verified layout — header row 2, data row 3+).
PAYMENT_COLUMNS = [
    'Client Name', 'Monthly Plan ($)', 'Billing Day', 'Last Paid Date',
    'Days Since Last Paid', 'Status', 'Days Overdue', 'Amount Overdue', 'Notes',
]

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_env() -> dict:
    """Parse the .env file into a dict (no external dependency)."""
    env: dict = {}
    if not os.path.exists(ENV_FILE):
        return env
    with open(ENV_FILE) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def master_sheet_id(client: dict = None) -> str:
    """Per-client override wins; else MASTER_SHEET_ID from .env / environment."""
    if client:
        override = (client.get('master_spreadsheet_id') or '').strip()
        if override:
            return override
    env = load_env()
    return env.get('MASTER_SHEET_ID',
                   os.environ.get('MASTER_SHEET_ID', '')).strip()


def _webapp_config() -> tuple:
    """(url, secret) for the Apps Script template generator web app, or ('','')."""
    env = load_env()
    url = env.get('TEMPLATE_WEBAPP_URL',
                  os.environ.get('TEMPLATE_WEBAPP_URL', '')).strip()
    secret = env.get('TEMPLATE_WEBAPP_SECRET',
                     os.environ.get('TEMPLATE_WEBAPP_SECRET', '')).strip()
    return url, secret


def trigger_template_generation(config=None, request_id=None,
                                timeout: int = 120) -> dict:
    """
    POST to the Apps Script web app to generate a client file.

    When ``config`` is supplied it is sent inline (config-in-POST), bypassing
    the master ⚙ tab round-trip and fixing the orphan-sheet race (#5).
    ``request_id`` enables idempotency on the Apps Script side — a repeated
    POST with the same id returns the cached result immediately.

    Raises RuntimeError on transport/auth failure or a script-side error.
    """
    url, secret = _webapp_config()
    if not url:
        raise RuntimeError('TEMPLATE_WEBAPP_URL is not set in .env — cannot '
                           'auto-generate. See docs/CLIENT_GENERATION.md.')
    payload: dict = {'secret': secret}
    if config is not None:
        payload['config'] = config
    if request_id is not None:
        payload['requestId'] = request_id
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        # Apps Script /exec answers a POST with a 302 to googleusercontent;
        # urllib follows it automatically and returns the final JSON body.
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Could not reach the generator web app: {exc}') from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Generator returned an unexpected (non-JSON) '
                           'response — re-check the deployment.') from exc
    if not data.get('ok'):
        raise RuntimeError(data.get('error', 'Generator reported an error.'))
    return data


def _load_clients(active_only: bool = False) -> list:
    """The client registry now lives in the shared database (was clients.yaml)."""
    return db.list_clients(active_only=active_only)


def extract_sheet_id(value: str) -> str:
    """Accept a full Sheets URL or a bare ID and return the spreadsheet ID."""
    value = (value or '').strip()
    if not value:
        return ''
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', value)
    if m:
        return m.group(1)
    # Bare ID (or anything without slashes) — take the first path-ish token.
    if '/' not in value and ' ' not in value:
        return value
    parsed = urlparse(value)
    parts = [p for p in parsed.path.split('/') if p]
    return parts[-1] if parts else value


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Day-first (dd/mm/yyyy) is the app's convention everywhere — UI labels and the
# generated sheet's dd/MM/yyyy number format. Day-first patterns MUST precede
# month-first, or a date like 07/06/2026 silently parses as July 6, not June 7.
_DATE_FORMATS = (
    '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
    '%d-%m-%Y', '%m-%d-%Y', '%Y/%m/%d',
    '%Y-%m-%d %H:%M:%S', '%B %d, %Y', '%b %d, %Y',
)


def _col(matrix: list) -> list:
    """Flat list of first-cell values from a value matrix."""
    return [row[0] if row else '' for row in (matrix or [])]


def _parse_floats(vals: list) -> list:
    out = []
    for v in vals:
        try:
            out.append(float(str(v).replace(',', '').strip()))
        except (ValueError, TypeError):
            out.append(None)
    return out


def _parse_dates(vals: list) -> list:
    out = []
    for v in vals:
        if not v or not str(v).strip():
            out.append(None)
            continue
        parsed = None
        for fmt in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(str(v).strip(), fmt).date()
                break
            except ValueError:
                pass
        out.append(parsed)
    return out


def _days_since_last(date_list: list):
    valid = [d for d in date_list if d is not None]
    if not valid:
        return None
    return (date.today() - max(valid)).days


# ---------------------------------------------------------------------------
# Concurrency + caching
#
# The dashboard reads several client sheets per page. A process-local TTL cache
# (cache.store) plus a bounded thread pool turn the old "~3 sequential Sheets
# calls per client on every navigation" into "fetch once per TTL window, in
# parallel" — the fix for the sluggish, inconsistent navigation (issue #7).
# Render runs a single worker, so the cache and pool are shared app-wide.
# ---------------------------------------------------------------------------

CACHE_TTL = 90  # seconds a client's fetched Sheets data stays fresh

# Persistent pool so each worker thread's Sheets service (built lazily below) is
# created once and reused across requests.
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix='sheets')
_thread_local = threading.local()


def _thread_service():
    """A Sheets service unique to the calling thread. httplib2 is not
    thread-safe, so parallel fetches must not share one service; each thread
    builds its own once and reuses it."""
    svc = getattr(_thread_local, 'service', None)
    if svc is None:
        svc = sc.new_service()
        _thread_local.service = svc
    return svc


def _card_bundle(spreadsheet_id: str) -> dict:
    """Cached per-sheet bundle for a client: weight/nutrition data + the
    last-logged workout. Loader runs on the calling thread's own service."""
    def load():
        service = _thread_service()
        return {
            'data': sc.fetch_client_data(service, spreadsheet_id),
            'last_logged': _last_logged_workout(service, spreadsheet_id),
        }
    return cache.store.get_or_fetch(f'card:{spreadsheet_id}', CACHE_TTL, load)


def _cached_payments(service, master_id: str) -> list:
    if not master_id:
        return []
    return cache.store.get_or_fetch(
        f'payments:{master_id}', CACHE_TTL,
        lambda: sc.fetch_payments(service, master_id))


def _cached_week_summary(service, spreadsheet_id: str) -> list:
    return cache.store.get_or_fetch(
        f'weeks:{spreadsheet_id}', CACHE_TTL,
        lambda: _week_summary(service, spreadsheet_id))


def _invalidate_client_cache(spreadsheet_id: str, master_id: str = '') -> None:
    """Drop cached reads for a sheet after a write, so the next page is fresh."""
    cache.store.invalidate(f'card:{spreadsheet_id}')
    cache.store.invalidate(f'weeks:{spreadsheet_id}')
    if master_id:
        cache.store.invalidate(f'payments:{master_id}')


# ---------------------------------------------------------------------------
# Payments (read from the master sheet, matched by client name)
# ---------------------------------------------------------------------------

def _payment_record(row: list) -> dict:
    """Map a raw Payments row to PAYMENT_COLUMNS."""
    return {
        PAYMENT_COLUMNS[i]: (row[i] if i < len(row) else '')
        for i in range(len(PAYMENT_COLUMNS))
    }


def _payment_for(name: str, payment_rows: list):
    """Find this client's payment record by name (case-insensitive)."""
    target = name.strip().lower()
    for row in payment_rows:
        if row and str(row[0]).strip().lower() == target:
            return _payment_record(row)
    return None


def _payment_display(record):
    """Return (display_str, css_class, is_overdue) for a payment record."""
    if not record:
        return 'No data', 'badge-gray', False
    status = str(record.get('Status', '')).upper().strip()
    if 'OVERDUE' in status:
        days = str(record.get('Days Overdue', '')).strip()
        m = re.search(r'(\d+)', days)
        suffix = f" {m.group(1)}d" if m else ''
        return f'OVERDUE{suffix}', 'badge-red', True
    if status in ('OK', 'PAID', 'DUE SOON'):
        cls = 'badge-yellow' if status == 'DUE SOON' else 'badge-green'
        return status, cls, False
    if not status or status == 'NO DATA':
        return 'No data', 'badge-gray', False
    return record.get('Status', ''), 'badge-gray', False


# ---------------------------------------------------------------------------
# Workout: last-logged across Week tabs (replaces the dead completion bar)
# ---------------------------------------------------------------------------

def _last_logged_workout(service, spreadsheet_id: str):
    """
    Most recent client-logged workout date across all Week tabs.

    Reads col G (client Date column) of every 'Week N' tab in one batchGet,
    returns {'date': 'dd/mm/yyyy', 'days_ago': N} or None if nothing logged.
    """
    try:
        tabs = [t for t in sc.get_sheet_tab_names(service, spreadsheet_id)
                if t.lower().startswith('week ')]
    except HttpError as exc:
        logger.error('Tab list failed for %s: %s', spreadsheet_id, exc)
        return None
    if not tabs:
        return None

    ranges = [f"'{t}'!G1:G" for t in tabs]
    data = sc.fetch_ranges(service, spreadsheet_id, ranges)

    latest = None
    for rng in ranges:
        for d in _parse_dates(_col(data.get(rng, []))):
            if d and (latest is None or d > latest):
                latest = d
    if latest is None:
        return None
    return {'date': latest.strftime('%d/%m/%Y'),
            'days_ago': (date.today() - latest).days}


def _week_summary(service, spreadsheet_id: str) -> list:
    """
    Per-week logged-session summary. For each Week tab, count session blocks
    (header rows like 'PUSH  —  Monday') and how many have a logged date in
    their client input area (col G). Returns a list of dicts for the table.
    """
    try:
        tabs = [t for t in sc.get_sheet_tab_names(service, spreadsheet_id)
                if t.lower().startswith('week ')]
    except HttpError:
        return []
    if not tabs:
        return []

    def week_num(t):
        m = re.search(r'(\d+)', t)
        return int(m.group(1)) if m else 0
    tabs.sort(key=week_num)

    ranges = [f"'{t}'!A1:K" for t in tabs]
    data = sc.fetch_ranges(service, spreadsheet_id, ranges)

    summary = []
    for tab, rng in zip(tabs, ranges):
        rows = data.get(rng, [])
        block_logged = []  # one bool per session block
        current_has = None
        for row in rows:
            first = (row[0] if row else '').strip() if row else ''
            # Session-block header rows look like "PUSH  —  Monday".
            if first and '—' in first and 'Exercise' not in first:
                if current_has is not None:
                    block_logged.append(current_has)
                current_has = False
            elif current_has is not None:
                # An exercise row with a non-empty Date (col G, index 6).
                if len(row) > 6 and str(row[6]).strip():
                    current_has = True
        if current_has is not None:
            block_logged.append(current_has)
        summary.append({
            'week': tab,
            'total': len(block_logged),
            'logged': sum(1 for b in block_logged if b),
        })
    return summary


# ---------------------------------------------------------------------------
# Status dot
# ---------------------------------------------------------------------------

def _status_dot(weight_dates, workout_days_ago, is_overdue: bool) -> str:
    if is_overdue:
        return 'red'
    w_days = _days_since_last(weight_dates)
    wo = workout_days_ago
    if w_days is None or w_days >= 5 or (wo is not None and wo >= 7):
        return 'red'
    if w_days == 4 or (wo is not None and wo in (5, 6)):
        return 'yellow'
    return 'green'


# ---------------------------------------------------------------------------
# Card / detail builders (variable names consumed by the templates)
# ---------------------------------------------------------------------------

def build_card(client: dict, data: dict, payment_rows: list,
               last_logged) -> dict:
    unit = client.get('weight_unit', 'kg')
    weight_dates = _parse_dates(_col(data.get('WeightDates', [])))
    weight_values = _parse_floats(_col(data.get('WeightValues', [])))

    record = _payment_for(client['name'], payment_rows)
    pay_display, pay_class, is_overdue = _payment_display(record)

    wo_days = last_logged['days_ago'] if last_logged else None
    status = _status_dot(weight_dates, wo_days, is_overdue)

    pairs = sorted(
        [(d, v) for d, v in zip(weight_dates, weight_values)
         if d is not None and v is not None],
        key=lambda x: x[0],
    )
    latest_weight = pairs[-1][1] if pairs else None
    weight_delta = (pairs[-1][1] - pairs[-2][1]) if len(pairs) >= 2 else None
    spark = pairs[-7:]

    return {
        'name': client['name'],
        'plan_usd': client.get('plan_usd', 0),
        'weight_unit': unit,
        'status': status,
        'latest_weight': latest_weight,
        'weight_delta': weight_delta,
        'spark_x': [str(d) for d, _ in spark],
        'spark_y': [v for _, v in spark],
        'last_logged': last_logged,
        'payment_display': pay_display,
        'payment_class': pay_class,
        'error': None,
    }


def build_detail(client: dict, data: dict, payment_rows: list,
                 last_logged, week_summary: list) -> dict:
    unit = client.get('weight_unit', 'kg')
    weight_dates = _parse_dates(_col(data.get('WeightDates', [])))
    weight_values = _parse_floats(_col(data.get('WeightValues', [])))
    weight_ma7 = _parse_floats(_col(data.get('WeightMA7', [])))
    daily_calories = _parse_floats(_col(data.get('WeightCalories', [])))
    sleep_values = _parse_floats(_col(data.get('WeightSleep', [])))

    record = _payment_for(client['name'], payment_rows)
    pay_display, pay_class, is_overdue = _payment_display(record)
    wo_days = last_logged['days_ago'] if last_logged else None
    status = _status_dot(weight_dates, wo_days, is_overdue)

    today = date.today()
    cutoff = today - timedelta(days=30)

    w30 = sorted(
        [(d, v, m) for d, v, m in zip(weight_dates, weight_values, weight_ma7)
         if d is not None and d >= cutoff and v is not None],
        key=lambda x: x[0],
    )

    # Calorie chart: real dated history from Weight!J, aligned to Weight!A.
    cal30 = sorted(
        [(d, c) for d, c in zip(weight_dates, daily_calories)
         if d is not None and d >= cutoff and c is not None],
        key=lambda x: x[0],
    )

    # Sleep (hours), dated by the same Weight!A column. Average the last 7 logged.
    sleep_by_date = {d: s for d, s in zip(weight_dates, sleep_values)
                     if d is not None and s is not None}
    recent_sleep = [s for _, s in sorted(sleep_by_date.items())][-7:]
    avg_sleep = round(sum(recent_sleep) / len(recent_sleep), 1) if recent_sleep else None

    all_weight = sorted(
        [(d, v) for d, v in zip(weight_dates, weight_values)
         if d is not None and v is not None],
        key=lambda x: x[0],
    )
    # Human-facing table → day-first dd/mm/yyyy (chart arrays below stay ISO so
    # Plotly treats them as real dates). Third element is sleep for that date.
    weight_table = [(d.strftime('%d/%m/%Y'), round(v, 1), sleep_by_date.get(d))
                    for d, v in all_weight[-14:]]

    return {
        'name': client['name'],
        'plan_usd': client.get('plan_usd', 0),
        'weight_unit': unit,
        'active': client.get('active', True),
        'status': status,
        'payment_display': pay_display,
        'payment_class': pay_class,
        'payment_record': record,
        'payment_columns': PAYMENT_COLUMNS,
        'last_logged': last_logged,
        'week_summary': week_summary,
        'weight_30d_dates': [str(d) for d, v, m in w30],
        'weight_30d_values': [v for d, v, m in w30],
        'weight_30d_ma7': [m for d, v, m in w30],
        'cal_dates': [str(d) for d, c in cal30],
        'cal_values': [c for d, c in cal30],
        'weight_table': weight_table,
        'avg_sleep': avg_sleep,
        'error': None,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _credentials_missing_page():
    return render_template('setup.html'), 200


def _error_card(client, msg):
    return {
        'name': client['name'],
        'plan_usd': client.get('plan_usd', 0),
        'weight_unit': client.get('weight_unit', 'kg'),
        'active': client.get('active', True),
        'status': 'red',
        'error': msg,
    }


@app.route('/')
def index():
    clients = _load_clients(active_only=True)
    try:
        service = sc.authenticate()
    except FileNotFoundError:
        return _credentials_missing_page()
    except sc.ReauthRequired:
        return redirect(url_for('reauth'))

    payment_rows = _cached_payments(service, master_sheet_id())

    def make_card(client):
        try:
            bundle = _card_bundle(client['spreadsheet_id'])
            return build_card(client, bundle['data'], payment_rows,
                              bundle['last_logged'])
        except HttpError as exc:
            logger.error('HttpError fetching %s: %s', client['name'], exc)
            return _error_card(client, 'Error fetching data — check Sheet ID')
        except Exception:
            logger.error('Unexpected error for %s', client['name'], exc_info=True)
            return _error_card(client, 'Unexpected error — see logs/dashboard.log')

    # Fetch every client concurrently (cache-backed); .map preserves order.
    cards = list(_POOL.map(make_card, clients)) if clients else []
    return render_template('index.html', cards=cards)


@app.route('/client/<path:name>')
def client_detail(name):
    name = unquote(name)
    clients = _load_clients()
    client = next((c for c in clients if c['name'] == name), None)
    if client is None:
        abort(404)

    try:
        service = sc.authenticate()
        bundle = _card_bundle(client['spreadsheet_id'])
        payment_rows = _cached_payments(service, master_sheet_id(client))
        week_summary = _cached_week_summary(service, client['spreadsheet_id'])
        detail = build_detail(client, bundle['data'], payment_rows,
                              bundle['last_logged'], week_summary)
    except FileNotFoundError:
        return _credentials_missing_page()
    except sc.ReauthRequired:
        return redirect(url_for('reauth'))
    except HttpError as exc:
        logger.error('HttpError detail for %s: %s', name, exc)
        detail = _error_card(client, 'Error fetching data — check Sheet ID')
    except Exception:
        logger.error('Unexpected error detail for %s', name, exc_info=True)
        detail = _error_card(client, 'Unexpected error — see logs/dashboard.log')

    return render_template('client.html', d=detail)


@app.route('/reauth')
def reauth():
    try:
        sc.authenticate(force=True)
        logger.info('Reauth successful')
        return redirect(url_for('index'))
    except Exception as exc:
        logger.error('Reauth failed: %s', exc)
        return (
            '<p style="font-family:monospace;padding:2rem">'
            f'Reauth failed: {exc}<br>Restart the server and try again.</p>'
        ), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


# ---------------------------------------------------------------------------
# In-app setup guide — /guide  (live "what's done / what's left" checklist)
# ---------------------------------------------------------------------------

def _setup_status() -> dict:
    """Snapshot of setup readiness, shown on the /guide page. No network calls."""
    master = master_sheet_id()
    webapp_url, webapp_secret = _webapp_config()
    sheets_ok = sc.sheets_configured()
    return {
        'sheets': sheets_ok,
        'sa_email': sc.service_account_email(),
        'master': bool(master),
        'master_tail': ('…' + master[-6:]) if master else '',
        'webapp': bool(webapp_url and webapp_secret),
        'client_count': len(_load_clients()),
        'ready': sheets_ok and bool(master),
    }


@app.route('/guide')
def guide():
    return render_template('guide.html', status=_setup_status())


# ---------------------------------------------------------------------------
# Workout Library (SQLite) — /library
# ---------------------------------------------------------------------------

def _parse_program_form(form) -> dict:
    """Build a program dict from posted form fields (used by new + edit).

    Sessions are now a dynamic ordered list (``session_label[]``) rather than
    a fixed Mon–Sun grid.  Each label becomes both ``day_name`` and
    ``workout_type`` so exercises keep linking by type unchanged.
    """
    labels = form.getlist('session_label')
    schedule = [
        {'day_order': i, 'day_name': lbl.strip(), 'workout_type': lbl.strip()}
        for i, lbl in enumerate(labels, 1)
        if lbl.strip()
    ]

    # Exercise rows are parallel arrays keyed by ex_<field>[].
    exercises = []
    types = form.getlist('ex_type')
    names = form.getlist('ex_name')
    sets_ = form.getlist('ex_sets')
    reps = form.getlist('ex_reps')
    notes = form.getlist('ex_notes')
    urls = form.getlist('ex_url')
    for i in range(len(names)):
        name = (names[i] or '').strip()
        if not name:
            continue
        exercises.append({
            'workout_type': (types[i] if i < len(types) else '').strip(),
            'position': i,
            'exercise': name,
            'target_sets': (sets_[i] if i < len(sets_) else '').strip(),
            'target_reps': (reps[i] if i < len(reps) else '').strip(),
            'coach_notes': (notes[i] if i < len(notes) else '').strip(),
            'tutorial_url': (urls[i] if i < len(urls) else '').strip(),
        })
    return {
        'name': (form.get('name') or '').strip(),
        'notes': (form.get('notes') or '').strip(),
        'schedule': schedule,
        'exercises': exercises,
    }


@app.route('/library')
def library():
    return render_template('library.html', programs=db.list_programs())


@app.route('/library/new', methods=['GET', 'POST'])
def library_new():
    if request.method == 'POST':
        program = _parse_program_form(request.form)
        if not program['name']:
            flash('Program name is required.', 'error')
            return render_template('library_edit.html', program=program,
                                   workout_types=db.WORKOUT_TYPES, mode='new')
        try:
            db.create_program(program)
            flash(f"Program '{program['name']}' created.", 'ok')
            return redirect(url_for('library'))
        except Exception as exc:
            logger.error('Create program failed: %s', exc)
            flash(f'Could not create program: {exc}', 'error')
    blank = {'name': '', 'notes': '', 'schedule': [], 'exercises': []}
    return render_template('library_edit.html', program=blank,
                           workout_types=db.WORKOUT_TYPES, mode='new')


@app.route('/library/<int:program_id>/edit', methods=['GET', 'POST'])
def library_edit(program_id):
    program = db.get_program(program_id)
    if program is None:
        abort(404)
    if request.method == 'POST':
        updated = _parse_program_form(request.form)
        if not updated['name']:
            flash('Program name is required.', 'error')
        else:
            try:
                db.update_program(program_id, updated)
                flash(f"Program '{updated['name']}' saved.", 'ok')
                return redirect(url_for('library'))
            except Exception as exc:
                logger.error('Update program failed: %s', exc)
                flash(f'Could not save program: {exc}', 'error')
        updated['id'] = program_id
        return render_template('library_edit.html', program=updated,
                               workout_types=db.WORKOUT_TYPES, mode='edit')
    # Pass schedule as-is (dynamic sessions); old day-grid programs will show
    # their workout_type as the session label — coach can clean up if desired.
    return render_template('library_edit.html', program=program,
                           workout_types=db.WORKOUT_TYPES, mode='edit')


@app.route('/library/<int:program_id>/delete', methods=['POST'])
def library_delete(program_id):
    if db.delete_program(program_id):
        flash('Program deleted.', 'ok')
    else:
        flash('Program not found.', 'error')
    return redirect(url_for('library'))


# ---------------------------------------------------------------------------
# New-client wizard — /clients/new
# ---------------------------------------------------------------------------

def _build_config_payload(data: dict) -> dict:
    """Build the config dict sent inline to the Apps Script (config-in-POST path).

    Shape matches ``normalizeConfig_`` in Code.gs — keep both in sync.
    """
    info = data['info']
    by_type: dict = {}
    for ex in data['exercises']:
        t = ex['workout_type']
        by_type.setdefault(t, []).append({
            'ex':    ex['exercise'],
            'sets':  ex['target_sets'],
            'reps':  ex['target_reps'],
            'notes': ex['coach_notes'],
            'link':  ex['tutorial_url'],
        })
    sessions = [
        {'label': s['workout_type'], 'exercises': by_type.get(s['workout_type'], [])}
        for s in data['schedule']
    ]
    t = data['targets']
    return {
        'info': {
            'name':    info['name'],
            'email':   info['email'],
            'program': info['program_name'],
            'goal':    info['goal'],
            'start':   info['start_date'],   # dd/mm/yyyy string
            'unit':    info['weight_unit'],
            'plan':    info['plan_usd'],
            'billing': info['billing_day'],
        },
        'sessions': sessions,
        'weeks':    data['weeks'],
        'targets':  [t['calories'], t['protein'], t['carbs'], t['fat'], t['fiber']],
        'sleepTarget': data.get('sleep_target', ''),
    }


# Admin-tab write targets in the master sheet (verified layout).
def _client_setup_updates(data: dict) -> list:
    """
    Build batchUpdate payload writing wizard data into the master admin tabs.
    Mirrors the verified master layout:
      ⚙ Client Info  B3..B10
      ⚙ Program Builder schedule C5:C11, exercises A15:F...
      ⚙ Week & RIR   A4:B.. (week, RIR)
      ⚙ Targets      B3:B7
    """
    info = data['info']
    updates = [
        {'range': "'⚙ Client Info'!B3:B10", 'values': [
            [info['name']], [info['email']], [info['program_name']],
            [info['goal']], [info['start_date']], [info['weight_unit']],
            [info['plan_usd']], [info['billing_day']],
        ]},
    ]

    # Program: weekly schedule (workout type per day, rows 5-11 = Mon-Sun).
    sched = {s['day_name']: s['workout_type'] for s in data['schedule']}
    sched_col = [[sched.get(d, 'Rest')] for d in db.DAYS]
    updates.append({'range': "'⚙ Program Builder'!C5:C11", 'values': sched_col})

    # Program: exercises table (A15 downward: Type, Exercise, Sets, Reps, Notes,
    # URL). The generator reads A15:F300, so we overwrite that WHOLE range —
    # padding with blanks — to wipe any leftover exercises from a previously
    # staged client instead of inheriting them.
    EX_ROWS = 300  # must match the generator's readConfig range (A15:F300)
    ex_rows = [[e['workout_type'], e['exercise'], e['target_sets'],
                e['target_reps'], e['coach_notes'], e['tutorial_url']]
               for e in data['exercises']]
    ex_rows = (ex_rows + [['', '', '', '', '', '']] * EX_ROWS)[:EX_ROWS]
    updates.append({'range': f"'⚙ Program Builder'!A15:F{15 + EX_ROWS - 1}",
                    'values': ex_rows})

    # Week & RIR (rows 4 downward: week number, target RIR). The generator reads
    # A4:B100, so overwrite that whole range with blank padding — otherwise a
    # previous client's extra weeks carry over and inflate the new client.
    WK_ROWS = 100  # must match the generator's readConfig range (A4:B100)
    rir_rows = [[w['week'], w['rir']] for w in data['weeks']]
    rir_rows = (rir_rows + [['', '']] * WK_ROWS)[:WK_ROWS]
    updates.append({'range': f"'⚙ Week & RIR'!A4:B{4 + WK_ROWS - 1}",
                    'values': rir_rows})

    # Targets (B2:B6 = calories, protein, carbs, fat, fiber).
    # NOTE: must match the Apps Script generator, which reads ⚙ Targets!B2:B6.
    t = data['targets']
    updates.append({'range': "'⚙ Targets'!B2:B6", 'values': [
        [t['calories']], [t['protein']], [t['carbs']], [t['fat']], [t['fiber']],
    ]})

    # Sleep target (hours) — a labelled row in the admin Targets tab, so it shows
    # in the master sheet and flows into the generated sheet's Sleep column header.
    updates.append({'range': "'⚙ Targets'!A7:B7",
                    'values': [['Sleep (hrs)', data.get('sleep_target', '')]]})
    return updates


def _parse_wizard_form(form) -> dict:
    """Collect all wizard fields into a structured dict."""
    info = {
        'name': (form.get('name') or '').strip(),
        'email': (form.get('email') or '').strip(),
        'program_name': (form.get('program_name') or '').strip(),
        'goal': (form.get('goal') or '').strip(),
        'start_date': (form.get('start_date') or '').strip(),
        'weight_unit': (form.get('weight_unit') or 'kg').strip(),
        'plan_usd': (form.get('plan_usd') or '').strip(),
        'billing_day': (form.get('billing_day') or '').strip(),
    }
    # Schedule + exercises reuse the library parser shape.
    prog = _parse_program_form(form)
    # Weeks & RIR.
    num_weeks = int(form.get('num_weeks') or 0)
    weeks = []
    for i in range(1, num_weeks + 1):
        weeks.append({'week': i,
                      'rir': (form.get(f'rir_{i}') or '').strip()})
    targets = {
        'calories': (form.get('calories') or '').strip(),
        'protein': (form.get('protein') or '').strip(),
        'carbs': (form.get('carbs') or '').strip(),
        'fat': (form.get('fat') or '').strip(),
        'fiber': (form.get('fiber') or '').strip(),
    }
    return {'info': info, 'schedule': prog['schedule'],
            'exercises': prog['exercises'], 'weeks': weeks, 'targets': targets,
            'sleep_target': (form.get('sleep_target') or '').strip()}


@app.route('/clients/new', methods=['GET', 'POST'])
def clients_new():
    action = request.form.get('action', '')

    if request.method == 'POST' and action == 'write_master':
        data = _parse_wizard_form(request.form)
        info = data['info']

        if not info['name']:
            flash('Client name is required.', 'error')
            return render_template('client_new.html', programs=db.list_programs(),
                                   workout_types=db.WORKOUT_TYPES,
                                   wrote_master=False, form=request.form)

        # Stable requestId for idempotency: reuse across retries in the same
        # wizard session so a network-timeout retry returns the cached sheet.
        request_id = session.get('wizard_request_id') or secrets.token_hex(16)
        session['wizard_request_id'] = request_id

        webapp_url, _ = _webapp_config()
        if webapp_url:
            # Config-in-POST path: send everything inline → no ⚙ tab write,
            # no orphan-sheet race, fully idempotent via requestId.
            try:
                config = _build_config_payload(data)
                result = trigger_template_generation(config=config,
                                                     request_id=request_id)
                new_id = extract_sheet_id(result.get('url', ''))
                if not new_id:
                    raise RuntimeError('Generator did not return a sheet URL.')
                if not db.client_exists(info['name']):
                    db.add_client({
                        'name': info['name'],
                        'spreadsheet_id': new_id,
                        'master_spreadsheet_id': '',
                        'plan_usd': _to_number(info.get('plan_usd'), 0),
                        'weight_unit': info.get('weight_unit', 'kg'),
                        'active': True,
                    })
                session.pop('wizard_request_id', None)
                shared = result.get('sharedWith') or ''
                tail = (f' Shared with {shared}.'
                        if shared and not shared.startswith('ERROR') else '')
                flash(f"Client sheet generated and registered.{tail}", 'ok')
                return redirect(url_for('client_detail', name=info['name']))
            except Exception as exc:
                logger.error('Auto-generate failed: %s', exc, exc_info=True)
                flash(f'Auto-generate failed: {exc} — you can write the data '
                      'to the master sheet and generate manually below.', 'error')
                return render_template('client_new.html', programs=db.list_programs(),
                                       workout_types=db.WORKOUT_TYPES,
                                       wrote_master=False, form=request.form)

        # Fallback: no web app configured — write the master ⚙ tabs and let
        # the coach run "Generate Client Template" manually.
        try:
            service = sc.authenticate()
            updates = _client_setup_updates(data)
            sc.batch_update_values(service, master_sheet_id(), updates)
        except FileNotFoundError:
            return _credentials_missing_page()
        except sc.ReauthRequired:
            return redirect(url_for('reauth'))
        except Exception as exc:
            logger.error('Wizard master write failed: %s', exc, exc_info=True)
            flash(f'Write to master sheet failed: {exc}', 'error')
            return render_template('client_new.html', programs=db.list_programs(),
                                   workout_types=db.WORKOUT_TYPES,
                                   wrote_master=False, form=request.form)

        flash('Data written to the master sheet. Now open the master '
              'spreadsheet and click Coach Tools → Generate Client '
              'Template, then paste the new sheet URL below.', 'ok')
        return render_template('client_new.html', programs=db.list_programs(),
                               workout_types=db.WORKOUT_TYPES,
                               wrote_master=True, form=request.form)

    if request.method == 'POST' and action == 'register':
        name = (request.form.get('reg_name') or '').strip()
        sheet_id = extract_sheet_id(request.form.get('reg_sheet') or '')
        if not name or not sheet_id:
            flash('Both client name and the new sheet URL/ID are required.', 'error')
            return render_template('client_new.html', programs=db.list_programs(),
                                   workout_types=db.WORKOUT_TYPES,
                                   wrote_master=True, form=request.form)
        if db.client_exists(name):
            flash(f"A client named '{name}' is already registered.", 'error')
            return redirect(url_for('client_detail', name=name))
        db.add_client({
            'name': name,
            'spreadsheet_id': sheet_id,
            'master_spreadsheet_id': '',
            'plan_usd': _to_number(request.form.get('reg_plan'), 0),
            'weight_unit': (request.form.get('reg_unit') or 'kg').strip(),
            'active': True,
        })
        flash(f"Client '{name}' registered.", 'ok')
        return redirect(url_for('client_detail', name=name))

    return render_template('client_new.html', programs=db.list_programs(),
                           workout_types=db.WORKOUT_TYPES,
                           wrote_master=False, form={})


@app.route('/clients/add', methods=['GET', 'POST'])
def clients_add():
    """
    Register an EXISTING Google Sheet as a client — no wizard, no master write.
    This is the path for sheets the coach already built by hand.
    """
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        sheet_id = extract_sheet_id(request.form.get('sheet') or '')
        if not name or not sheet_id:
            flash('Both a client name and the sheet URL/ID are required.', 'error')
            return render_template('client_add.html', form=request.form)

        if db.client_exists(name):
            flash(f"A client named '{name}' is already registered.", 'error')
            return render_template('client_add.html', form=request.form)

        # Best-effort access check so a typo'd ID surfaces now, not on the card.
        try:
            service = sc.authenticate()
            sc.get_sheet_tab_names(service, sheet_id)
        except FileNotFoundError:
            return _credentials_missing_page()
        except sc.ReauthRequired:
            return redirect(url_for('reauth'))
        except Exception as exc:
            logger.warning('Add-client access check failed for %s: %s', sheet_id, exc)
            flash('Registered, but the sheet could not be opened — check the URL '
                  'and that the signed-in Google account has access.', 'error')

        db.add_client({
            'name': name,
            'spreadsheet_id': sheet_id,
            'master_spreadsheet_id': (request.form.get('master_sheet') or '').strip(),
            'plan_usd': _to_number(request.form.get('plan'), 0),
            'weight_unit': (request.form.get('weight_unit') or 'kg').strip(),
            'active': True,
        })
        flash(f"Client '{name}' added.", 'ok')
        return redirect(url_for('client_detail', name=name))

    return render_template('client_add.html', form={})


# ---------------------------------------------------------------------------
# Client management — edit, deactivate, delete (issue #6: real CRUD + cleanup)
# ---------------------------------------------------------------------------

def _purge_client_artifacts(name: str) -> None:
    """Remove ALL name-scoped data for a deleted client: Cronometer creds and
    the cached nutrition view. The Google Sheet in Drive is left untouched."""
    try:
        secrets_store.delete_credentials(name)
    except Exception:
        logger.warning('Could not clear creds for deleted client %s', name, exc_info=True)
    try:
        db.kv_delete(_foods_cache_key(name))
    except Exception:
        logger.warning('Could not clear nutrition cache for %s', name, exc_info=True)


def _rename_client_artifacts(old_name: str, new_name: str) -> None:
    """Move name-scoped data when a client is renamed, so creds + nutrition
    cache stay attached instead of being orphaned — the exact issue #6 bug."""
    try:
        secrets_store.rename_credentials(old_name, new_name)
    except Exception:
        logger.warning('Could not move creds %s -> %s', old_name, new_name, exc_info=True)
    try:
        raw = db.kv_get(_foods_cache_key(old_name))
        if raw:
            db.kv_set(_foods_cache_key(new_name), raw)
            db.kv_delete(_foods_cache_key(old_name))
    except Exception:
        logger.warning('Could not move nutrition cache %s -> %s', old_name, new_name, exc_info=True)


@app.route('/client/<path:name>/edit', methods=['GET', 'POST'])
def client_edit(name):
    name = unquote(name)
    client = db.get_client_by_name(name)
    if client is None:
        abort(404)

    if request.method == 'POST':
        new_name = (request.form.get('name') or '').strip()
        new_sheet = (extract_sheet_id(request.form.get('sheet') or '')
                     or client['spreadsheet_id'])
        if not new_name:
            flash('Client name is required.', 'error')
            return render_template('client_edit.html', client=client, form=request.form)
        # Renaming onto a DIFFERENT existing client would collide (name is unique).
        if new_name.lower() != name.lower() and db.client_exists(new_name):
            flash(f"A client named '{new_name}' already exists.", 'error')
            return render_template('client_edit.html', client=client, form=request.form)

        db.update_client(name, {
            'name': new_name,
            'spreadsheet_id': new_sheet,
            'master_spreadsheet_id': (request.form.get('master_sheet') or '').strip(),
            'plan_usd': _to_number(request.form.get('plan'), 0),
            'weight_unit': (request.form.get('weight_unit') or 'kg').strip(),
        })
        if new_name.lower() != name.lower():
            _rename_client_artifacts(name, new_name)
        _invalidate_client_cache(client['spreadsheet_id'], master_sheet_id(client))
        _invalidate_client_cache(new_sheet)
        flash('Client updated.', 'ok')
        return redirect(url_for('client_detail', name=new_name))

    return render_template('client_edit.html', client=client, form={})


@app.route('/client/<path:name>/toggle', methods=['POST'])
def client_toggle_active(name):
    name = unquote(name)
    client = db.get_client_by_name(name)
    if client is None:
        abort(404)
    new_state = not client.get('active', True)
    db.set_client_active(name, new_state)
    flash(f"{name} {'reactivated' if new_state else 'deactivated'}.", 'ok')
    return redirect(url_for('client_detail', name=name))


@app.route('/client/<path:name>/delete', methods=['POST'])
def client_delete(name):
    name = unquote(name)
    client = db.get_client_by_name(name)
    if client is None:
        abort(404)
    _invalidate_client_cache(client['spreadsheet_id'], master_sheet_id(client))
    db.delete_client(name)
    _purge_client_artifacts(name)
    flash(f"Removed '{name}' from the dashboard. Their Google Sheet was left "
          "untouched in Drive.", 'ok')
    return redirect(url_for('index'))


@app.route('/library/<int:program_id>/json')
def library_json(program_id):
    """Return a program as JSON so the wizard can prefill from a preset."""
    program = db.get_program(program_id)
    if program is None:
        abort(404)
    return jsonify(program)


# ---------------------------------------------------------------------------
# Client log entry — /client/<name>/log
# ---------------------------------------------------------------------------

def _to_number(value, default=None):
    try:
        f = float(str(value).replace(',', '').strip())
        return int(f) if f.is_integer() else f
    except (ValueError, TypeError, AttributeError):
        return default


def _weight_row_for_date(service, spreadsheet_id: str, target: date):
    """Find the 1-based Weight-tab row whose col-A date matches target."""
    data = sc.fetch_ranges(service, spreadsheet_id, ['Weight!A2:A'])
    dates = _parse_dates(_col(data.get('Weight!A2:A', [])))
    for i, d in enumerate(dates):
        if d == target:
            return i + 2  # +2: A2 is row 2
    return None


@app.route('/client/<path:name>/log', methods=['GET', 'POST'])
def client_log(name):
    name = unquote(name)
    clients = _load_clients()
    client = next((c for c in clients if c['name'] == name), None)
    if client is None:
        abort(404)

    if request.method == 'POST':
        kind = request.form.get('kind', '')
        try:
            service = sc.authenticate()
        except FileNotFoundError:
            return _credentials_missing_page()
        except sc.ReauthRequired:
            return redirect(url_for('reauth'))

        if kind == 'weight':
            raw_date = (request.form.get('date') or '').strip()
            weight = (request.form.get('weight') or '').strip()
            parsed = _parse_dates([raw_date])[0]
            if not parsed or not weight:
                flash('A valid date and weight are required.', 'error')
            else:
                row = _weight_row_for_date(service, client['spreadsheet_id'], parsed)
                if row is None:
                    flash(f'No row for {raw_date} exists in the Weight tab.', 'error')
                else:
                    try:
                        sc.batch_update_values(
                            service, client['spreadsheet_id'],
                            [{'range': f'Weight!B{row}',
                              'values': [[_to_number(weight, weight)]]}])
                        flash(f'Logged {weight} {client.get("weight_unit", "kg")} '
                              f'for {raw_date}.', 'ok')
                    except Exception as exc:
                        logger.error('Weight write failed: %s', exc)
                        flash(f'Weight write failed: {exc}', 'error')

        elif kind == 'sleep':
            raw_date = (request.form.get('date') or '').strip()
            hours = (request.form.get('sleep') or '').strip()
            parsed = _parse_dates([raw_date])[0]
            if not parsed or not hours:
                flash('A valid date and sleep hours are required.', 'error')
            else:
                row = _weight_row_for_date(service, client['spreadsheet_id'], parsed)
                if row is None:
                    flash(f'No row for {raw_date} exists in the Weight tab.', 'error')
                else:
                    try:
                        sc.batch_update_values(
                            service, client['spreadsheet_id'],
                            [{'range': f'Weight!L{row}',
                              'values': [[_to_number(hours, hours)]]}])
                        flash(f'Logged {hours} h sleep for {raw_date}.', 'ok')
                    except Exception as exc:
                        logger.error('Sleep write failed: %s', exc)
                        flash(f'Sleep write failed: {exc}', 'error')

        elif kind == 'payment':
            paid_date = (request.form.get('paid_date') or '').strip()
            parsed = _parse_dates([paid_date])[0]
            if not parsed:
                flash('A valid paid date is required.', 'error')
            else:
                mid = master_sheet_id(client)
                rows = sc.fetch_payments(service, mid)
                target = name.strip().lower()
                row_idx = None
                for i, r in enumerate(rows):
                    if r and str(r[0]).strip().lower() == target:
                        row_idx = i + 3  # Payments data starts at row 3
                        break
                if row_idx is None:
                    flash('No matching row in the master Payments tab.', 'error')
                else:
                    try:
                        sc.batch_update_values(
                            service, mid,
                            [{'range': f'Payments!D{row_idx}',
                              'values': [[parsed.strftime('%Y-%m-%d')]]}])
                        flash(f'Marked payment received on {paid_date}.', 'ok')
                    except Exception as exc:
                        logger.error('Payment write failed: %s', exc)
                        flash(f'Payment write failed: {exc}', 'error')

        # A write just happened — drop cached reads so the next view is fresh.
        _invalidate_client_cache(client['spreadsheet_id'], master_sheet_id(client))
        return redirect(url_for('client_log', name=name))

    return render_template('client_log.html', client=client,
                           today=date.today().strftime('%d/%m/%Y'))


# ---------------------------------------------------------------------------
# Cronometer nutrition sync — /client/<name>/cronometer
# ---------------------------------------------------------------------------

@app.route('/client/<path:name>/cronometer', methods=['GET', 'POST'])
def client_cronometer(name):
    name = unquote(name)
    clients = _load_clients()
    client = next((c for c in clients if c['name'] == name), None)
    if client is None:
        abort(404)

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'save':
            email = (request.form.get('cron_email') or '').strip()
            password = (request.form.get('cron_password') or '').strip()
            if not email or not password:
                flash('Both the Cronometer email and password are required.', 'error')
            else:
                secrets_store.set_credentials(name, email, password)
                flash('Cronometer credentials saved (encrypted in the shared database).', 'ok')

        elif action == 'delete':
            secrets_store.delete_credentials(name)
            flash('Cronometer credentials removed.', 'ok')

        elif action == 'sync':
            creds = secrets_store.get_credentials(name)
            if not creds:
                flash('Add the client\'s Cronometer login first.', 'error')
                return redirect(url_for('client_cronometer', name=name))
            try:
                service = sc.authenticate()
            except FileNotFoundError:
                return _credentials_missing_page()
            except sc.ReauthRequired:
                return redirect(url_for('reauth'))
            try:
                user_days = _to_number(request.form.get('days'), 14) or 14
                # Align the pull window to the dates the Weight tab actually
                # covers, so recent logged days line up with its fixed dated grid.
                date_rows = nutrition_sync.weight_date_rows(
                    service, client['spreadsheet_id'])
                pull_days = nutrition_sync.days_to_cover(date_rows, int(user_days))
                rows = cronometer_api.fetch_daily_nutrition(
                    creds['email'], creds['password'], days=int(pull_days))
                result = nutrition_sync.sync_to_sheet(
                    service, client['spreadsheet_id'], rows, date_rows=date_rows)
                _invalidate_client_cache(client['spreadsheet_id'])
                msg = f"Synced {result['written']} day(s) of calories into the Weight tab."
                if result['skipped']:
                    span = (f", which covers {result['range_str']}"
                            if result.get('range_str') else "")
                    msg += (f" {result['skipped']} Cronometer day(s) had no matching "
                            f"date row in the Weight tab{span}.")
                flash(msg, 'ok' if result['written'] else 'error')
            except Exception as exc:
                logger.error('Cronometer sync failed for %s: %s', name, exc,
                             exc_info=True)
                flash(f'Cronometer sync failed: {exc}', 'error')

        return redirect(url_for('client_cronometer', name=name))

    return render_template('client_cronometer.html', client=client,
                           has_creds=secrets_store.has_credentials(name))


def _foods_cache_key(name: str) -> str:
    return f'cron_foods:{name}'


def _foods_cache_get(name: str):
    """Return (view_dict, fetched_at_str) from the DB, or (None, None)."""
    raw = db.kv_get(_foods_cache_key(name))
    if not raw:
        return None, None
    try:
        data = json.loads(raw)
        return data.get('view'), data.get('fetched_at')
    except Exception:
        return None, None


def _foods_cache_set(name: str, view: dict) -> None:
    payload = json.dumps({
        'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'view': view,
    })
    db.kv_set(_foods_cache_key(name), payload)


def _foods_merge(cached: dict, fresh: dict) -> dict:
    """Overlay fresh days onto cached days; prune to last 31 days, newest-first."""
    by_date = {}
    for day in (cached.get('days') or []):
        by_date[day['date']] = day
    for day in (fresh.get('days') or []):
        by_date[day['date']] = day  # fresh wins

    cutoff = date.today() - timedelta(days=31)

    def _parse_dmy(s):
        try:
            d_, m_, y_ = s.split('/')
            return date(int(y_), int(m_), int(d_))
        except Exception:
            return date.min

    kept = sorted(
        [d for d in by_date.values() if _parse_dmy(d['date']) >= cutoff],
        key=lambda d: _parse_dmy(d['date']),
        reverse=True,
    )
    return {'days': kept, 'count': sum(len(d['foods']) for d in kept)}


@app.route('/client/<path:name>/cronometer/foods')
def client_cronometer_foods(name):
    """Show the full per-food Cronometer log. Caches up to 31 days in the DB."""
    name = unquote(name)
    client = next((c for c in _load_clients() if c['name'] == name), None)
    if client is None:
        abort(404)

    days = _to_number(request.args.get('days'), 7) or 7
    do_reload = request.args.get('reload') == '1'

    creds = secrets_store.get_credentials(name)
    cached_view, fetched_at = _foods_cache_get(name)
    view, error = cached_view, None

    if not creds:
        error = "Add this client's Cronometer login first (on the Cronometer page)."
    elif do_reload or cached_view is None:
        try:
            parsed = cronometer_api.fetch_servings(
                creds['email'], creds['password'], days=int(days))
            fresh = cronometer_client.structure_servings(parsed)
            view = _foods_merge(cached_view or {}, fresh) if cached_view else fresh
            _foods_cache_set(name, view)
            fetched_at = 'just now'
        except Exception as exc:
            logger.error('Cronometer foods fetch failed for %s: %s', name, exc,
                         exc_info=True)
            error = f'Could not load foods: {exc}'
            # fall back to whatever was cached

    return render_template('cronometer_foods.html', client=client, view=view,
                           error=error, days=int(days), fetched_at=fetched_at)


@app.route('/client/<path:name>/nutrition')
def client_nutrition(name):
    """Full nutrition page: calendar date-picker + per-day detail from Cronometer cache."""
    name = unquote(name)
    client = next((c for c in _load_clients() if c['name'] == name), None)
    if client is None:
        abort(404)

    cached_view, fetched_at = _foods_cache_get(name)

    # Pull 30-day calorie history + macro targets from the sheet in one call.
    cal_by_date: dict = {}
    targets: dict = {}
    try:
        service = sc.authenticate()
        extra = sc.fetch_ranges(service, client['spreadsheet_id'],
                                ['Weight!A2:A', 'Weight!J2:J',
                                 "'⚙ Targets'!B2:B6"])
        wdates = _parse_dates(_col(extra.get('Weight!A2:A', [])))
        wcals  = _parse_floats(_col(extra.get('Weight!J2:J', [])))
        today_d = date.today()
        cutoff  = today_d - timedelta(days=31)
        for d_, c_ in zip(wdates, wcals):
            if d_ is not None and c_ is not None and d_ >= cutoff:
                cal_by_date[d_.isoformat()] = round(c_, 1)

        tvals = _col(extra.get("'⚙ Targets'!B2:B6", []))
        tfl   = _parse_floats(tvals)
        keys  = ['calories', 'protein', 'carbs', 'fat', 'fiber']
        targets = {k: tfl[i] for i, k in enumerate(keys) if i < len(tfl) and tfl[i] is not None}
    except Exception as exc:
        logger.warning('Nutrition page sheet fetch failed for %s: %s', name, exc)

    return render_template('cronometer_nutrition.html',
                           client=client,
                           view=cached_view,
                           fetched_at=fetched_at,
                           cal_by_date=cal_by_date,
                           targets=targets)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
