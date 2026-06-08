import os
import re
import json
import logging
import logging.handlers
import urllib.request
import urllib.error
import yaml
from datetime import date, datetime, timedelta
from urllib.parse import unquote, urlparse

from flask import (Flask, render_template, redirect, url_for, jsonify, abort,
                   request, flash)
from googleapiclient.errors import HttpError

import sheets_client as sc
import db
import secrets_store
import cronometer_api
import nutrition_sync

# ---------------------------------------------------------------------------
# Paths + app + logging
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENTS_FILE = os.path.join(BASE_DIR, 'clients.yaml')
ENV_FILE = os.path.join(BASE_DIR, '.env')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'coach-abood-local-secret')

# Ensure the local workout-library DB exists (idempotent).
try:
    db.init_db()
except Exception:
    pass

os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
_fh = logging.handlers.RotatingFileHandler(
    os.path.join(BASE_DIR, 'logs', 'dashboard.log'),
    maxBytes=5 * 1024 * 1024, backupCount=3,
)
_fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_fh])
logger = logging.getLogger(__name__)

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


def trigger_template_generation(timeout: int = 120) -> dict:
    """
    POST to the Apps Script web app to generate a client file from the master
    admin tabs. Returns the parsed JSON {ok, url, id, fileName, sharedWith}.

    Raises RuntimeError on transport/auth failure or if the script reports an
    error, so the caller can surface a clean message.
    """
    url, secret = _webapp_config()
    if not url:
        raise RuntimeError('TEMPLATE_WEBAPP_URL is not set in .env — cannot '
                           'auto-generate. See docs/CLIENT_GENERATION.md.')
    body = json.dumps({'secret': secret}).encode('utf-8')
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


def _load_clients() -> list:
    if not os.path.exists(CLIENTS_FILE):
        return []
    with open(CLIENTS_FILE) as fh:
        return (yaml.safe_load(fh) or {}).get('clients', [])


def _save_clients(clients: list) -> None:
    """Persist the client registry back to clients.yaml, preserving the header."""
    with open(CLIENTS_FILE, 'w') as fh:
        yaml.safe_dump({'clients': clients}, fh, sort_keys=False,
                       allow_unicode=True, default_flow_style=False)


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

    all_weight = sorted(
        [(d, v) for d, v in zip(weight_dates, weight_values)
         if d is not None and v is not None],
        key=lambda x: x[0],
    )
    # Human-facing table → day-first dd/mm/yyyy (chart arrays below stay ISO so
    # Plotly treats them as real dates).
    weight_table = [(d.strftime('%d/%m/%Y'), round(v, 1)) for d, v in all_weight[-14:]]

    return {
        'name': client['name'],
        'plan_usd': client.get('plan_usd', 0),
        'weight_unit': unit,
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
        'status': 'red',
        'error': msg,
    }


@app.route('/')
def index():
    clients = _load_clients()
    try:
        service = sc.authenticate()
    except FileNotFoundError:
        return _credentials_missing_page()
    except sc.ReauthRequired:
        return redirect(url_for('reauth'))

    payment_rows = sc.fetch_payments(service, master_sheet_id())

    cards = []
    for client in clients:
        try:
            data = sc.fetch_client_data(service, client['spreadsheet_id'])
            last_logged = _last_logged_workout(service, client['spreadsheet_id'])
            cards.append(build_card(client, data, payment_rows, last_logged))
        except HttpError as exc:
            logger.error('HttpError fetching %s: %s', client['name'], exc)
            cards.append(_error_card(client, 'Error fetching data — check Sheet ID'))
        except Exception:
            logger.error('Unexpected error for %s', client['name'], exc_info=True)
            cards.append(_error_card(client, 'Unexpected error — see logs/dashboard.log'))

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
        data = sc.fetch_client_data(service, client['spreadsheet_id'])
        payment_rows = sc.fetch_payments(service, master_sheet_id(client))
        last_logged = _last_logged_workout(service, client['spreadsheet_id'])
        week_summary = _week_summary(service, client['spreadsheet_id'])
        detail = build_detail(client, data, payment_rows, last_logged, week_summary)
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
    env = load_env()
    master = env.get('MASTER_SHEET_ID',
                     os.environ.get('MASTER_SHEET_ID', '')).strip()
    webapp_url, webapp_secret = _webapp_config()
    creds_ok = os.path.exists(sc.CREDS_PATH)
    token_ok = os.path.exists(sc.TOKEN_PATH)

    # Best-effort token expiry read (no network): the stored JSON has 'expiry'.
    token_state = 'missing'
    if token_ok:
        token_state = 'present'
        try:
            with open(sc.TOKEN_PATH) as fh:
                tok = json.load(fh)
            exp = tok.get('expiry', '')
            if exp:
                # stored as e.g. 2026-06-08T12:00:00Z or with microseconds
                exp_dt = datetime.strptime(exp.replace('Z', '')[:19],
                                           '%Y-%m-%dT%H:%M:%S')
                token_state = 'expired' if exp_dt < datetime.utcnow() else 'valid'
        except Exception:  # noqa: BLE001 — presence already recorded
            pass

    return {
        'credentials': creds_ok,
        'token': token_ok,
        'token_state': token_state,
        'master': bool(master),
        'master_tail': ('…' + master[-6:]) if master else '',
        'webapp': bool(webapp_url and webapp_secret),
        'client_count': len(_load_clients()),
        'ready': creds_ok and bool(master),
    }


@app.route('/guide')
def guide():
    return render_template('guide.html', status=_setup_status())


# ---------------------------------------------------------------------------
# Workout Library (SQLite) — /library
# ---------------------------------------------------------------------------

def _parse_program_form(form) -> dict:
    """Build a program dict from posted form fields (used by new + edit)."""
    schedule = []
    for i, day in enumerate(db.DAYS, start=1):
        wt = form.get(f'schedule_{day}', 'Rest') or 'Rest'
        schedule.append({'day_order': i, 'day_name': day, 'workout_type': wt})

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
                                   days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                                   mode='new')
        try:
            db.create_program(program)
            flash(f"Program '{program['name']}' created.", 'ok')
            return redirect(url_for('library'))
        except Exception as exc:
            logger.error('Create program failed: %s', exc)
            flash(f'Could not create program: {exc}', 'error')
    blank = {'name': '', 'notes': '',
             'schedule': [{'day_order': i, 'day_name': d, 'workout_type': 'Rest'}
                          for i, d in enumerate(db.DAYS, start=1)],
             'exercises': []}
    return render_template('library_edit.html', program=blank,
                           days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                           mode='new')


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
                               days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                               mode='edit')
    # Normalise schedule to all 7 days for the editor grid.
    sched_by_day = {s['day_name']: s['workout_type'] for s in program['schedule']}
    program['schedule'] = [
        {'day_order': i, 'day_name': d,
         'workout_type': sched_by_day.get(d, 'Rest')}
        for i, d in enumerate(db.DAYS, start=1)
    ]
    return render_template('library_edit.html', program=program,
                           days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                           mode='edit')


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
            'exercises': prog['exercises'], 'weeks': weeks, 'targets': targets}


@app.route('/clients/new', methods=['GET', 'POST'])
def clients_new():
    action = request.form.get('action', '')

    if request.method == 'POST' and action == 'write_master':
        data = _parse_wizard_form(request.form)
        info = data['info']

        # 1) Fill the master admin tabs (the Apps Script reads these).
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
                                   days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                                   wrote_master=False, form=request.form)

        # 2) If the generator web app is configured, do the whole thing in one
        #    click: run the Apps Script, grab the new sheet, auto-register it.
        webapp_url, _ = _webapp_config()
        if webapp_url:
            try:
                result = trigger_template_generation()
                new_id = extract_sheet_id(result.get('url', ''))
                if not new_id:
                    raise RuntimeError('Generator did not return a sheet URL.')
                clients = _load_clients()
                if not any(c.get('name', '').strip().lower()
                           == info['name'].strip().lower() for c in clients):
                    clients.append({
                        'name': info['name'],
                        'spreadsheet_id': new_id,
                        'master_spreadsheet_id': '',
                        'plan_usd': _to_number(info.get('plan_usd'), 0),
                        'weight_unit': info.get('weight_unit', 'kg'),
                        'active': True,
                    })
                    _save_clients(clients)
                shared = result.get('sharedWith') or ''
                tail = (f' Shared with {shared}.'
                        if shared and not shared.startswith('ERROR') else '')
                flash(f"Client sheet generated and registered.{tail}", 'ok')
                return redirect(url_for('client_detail', name=info['name']))
            except Exception as exc:
                logger.error('Auto-generate failed: %s', exc, exc_info=True)
                flash(f'Master sheet updated, but auto-generate failed: {exc} '
                      'You can run Coach Tools → Generate Client Template '
                      'manually and register the sheet below.', 'error')
                return render_template('client_new.html', programs=db.list_programs(),
                                       days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                                       wrote_master=True, form=request.form)

        # 3) No web app configured — fall back to the manual generate+register.
        flash('Data written to the master sheet. Now open the master '
              'spreadsheet and click Coach Tools → Generate Client '
              'Template, then paste the new sheet URL below.', 'ok')
        return render_template('client_new.html', programs=db.list_programs(),
                               days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                               wrote_master=True, form=request.form)

    if request.method == 'POST' and action == 'register':
        name = (request.form.get('reg_name') or '').strip()
        sheet_id = extract_sheet_id(request.form.get('reg_sheet') or '')
        if not name or not sheet_id:
            flash('Both client name and the new sheet URL/ID are required.', 'error')
            return render_template('client_new.html', programs=db.list_programs(),
                                   days=db.DAYS, workout_types=db.WORKOUT_TYPES,
                                   wrote_master=True, form=request.form)
        clients = _load_clients()
        clients.append({
            'name': name,
            'spreadsheet_id': sheet_id,
            'master_spreadsheet_id': '',
            'plan_usd': _to_number(request.form.get('reg_plan'), 0),
            'weight_unit': (request.form.get('reg_unit') or 'kg').strip(),
            'active': True,
        })
        _save_clients(clients)
        flash(f"Client '{name}' registered.", 'ok')
        return redirect(url_for('client_detail', name=name))

    return render_template('client_new.html', programs=db.list_programs(),
                           days=db.DAYS, workout_types=db.WORKOUT_TYPES,
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

        clients = _load_clients()
        if any(c.get('name', '').strip().lower() == name.lower() for c in clients):
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

        clients.append({
            'name': name,
            'spreadsheet_id': sheet_id,
            'master_spreadsheet_id': (request.form.get('master_sheet') or '').strip(),
            'plan_usd': _to_number(request.form.get('plan'), 0),
            'weight_unit': (request.form.get('weight_unit') or 'kg').strip(),
            'active': True,
        })
        _save_clients(clients)
        flash(f"Client '{name}' added.", 'ok')
        return redirect(url_for('client_detail', name=name))

    return render_template('client_add.html', form={})


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
                        flash(f'Logged {weight} {client.get("weight_unit","kg")} '
                              f'for {raw_date}.', 'ok')
                    except Exception as exc:
                        logger.error('Weight write failed: %s', exc)
                        flash(f'Weight write failed: {exc}', 'error')

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
                flash('Cronometer credentials saved (encrypted on this machine).', 'ok')

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
                days = _to_number(request.form.get('days'), 14) or 14
                rows = cronometer_api.fetch_daily_nutrition(
                    creds['email'], creds['password'], days=int(days))
                result = nutrition_sync.sync_to_sheet(
                    service, client['spreadsheet_id'], rows)
                flash(f"Synced {result['written']} day(s) of calories "
                      f"({result['skipped']} skipped — no matching date row).", 'ok')
            except Exception as exc:
                logger.error('Cronometer sync failed for %s: %s', name, exc,
                             exc_info=True)
                flash(f'Cronometer sync failed: {exc}', 'error')

        return redirect(url_for('client_cronometer', name=name))

    return render_template('client_cronometer.html', client=client,
                           has_creds=secrets_store.has_credentials(name))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
