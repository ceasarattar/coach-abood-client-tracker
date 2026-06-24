"""Integration tests for Flask routes (credential-free flows)."""
import pytest
import json


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _csrf(client):
    """Ensure CSRF token exists in session and return it."""
    with client.session_transaction() as s:
        if 'csrf_token' not in s:
            s['csrf_token'] = 'TEST_TOK'
        return s['csrf_token']


# ---------------------------------------------------------------------------
# Status-code smoke tests
# ---------------------------------------------------------------------------

class TestStaticRoutes:
    def test_library_list(self, client):
        r = client.get('/library')
        assert r.status_code == 200

    def test_library_new_get(self, client):
        r = client.get('/library/new')
        assert r.status_code == 200

    def test_wizard_new_get(self, client):
        r = client.get('/clients/new')
        assert r.status_code == 200

    def test_add_client_get(self, client):
        r = client.get('/clients/add')
        assert r.status_code == 200

    def test_health(self, client):
        r = client.get('/health')
        assert r.status_code == 200

    def test_404(self, client):
        r = client.get('/does-not-exist-xyz')
        assert r.status_code == 404

    def test_login_redirects_when_no_passcode(self, client):
        """With no WEBAPP_PASSCODE set, /login redirects away."""
        r = client.get('/login')
        assert r.status_code == 302

    def test_guide(self, client):
        r = client.get('/guide')
        # Either renders or redirects if not authed — both are fine; just no 5xx.
        assert r.status_code in (200, 302)


# ---------------------------------------------------------------------------
# Branding checks
# ---------------------------------------------------------------------------

class TestBranding:
    def test_library_coach_khader(self, client):
        r = client.get('/library')
        assert b'Coach Khader' in r.data
        assert b'Coach Abood' not in r.data

    def test_library_new_coach_khader(self, client):
        r = client.get('/library/new')
        assert b'Coach Khader' in r.data
        assert b'Coach Abood' not in r.data

    def test_wizard_coach_khader(self, client):
        r = client.get('/clients/new')
        assert b'Coach Khader' in r.data
        assert b'Coach Abood' not in r.data

    def test_add_client_coach_khader(self, client):
        r = client.get('/clients/add')
        assert b'Coach Khader' in r.data
        assert b'Coach Abood' not in r.data


# ---------------------------------------------------------------------------
# Session-list UI checks (no fixed Mon–Sun grid)
# ---------------------------------------------------------------------------

class TestSessionListUI:
    def test_library_new_has_session_list(self, client):
        r = client.get('/library/new')
        html = r.data
        assert b'session-list' in html
        assert b'session_label' in html
        assert b'session-labels' in html
        assert b'Add session' in html

    def test_library_new_no_old_grid(self, client):
        r = client.get('/library/new')
        html = r.data
        assert b'schedule_Monday' not in html
        assert b'sched-grid' not in html
        assert b'Weekly schedule' not in html

    def test_wizard_has_session_list(self, client):
        r = client.get('/clients/new')
        html = r.data
        assert b'session-list' in html
        assert b'session_label' in html
        assert b'Training sessions' in html

    def test_wizard_no_old_grid(self, client):
        r = client.get('/clients/new')
        html = r.data
        assert b'schedule_Monday' not in html
        assert b'sched-grid' not in html

    def test_wizard_has_lock_submit(self, client):
        r = client.get('/clients/new')
        assert b'lockSubmit' in r.data


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

class TestCSRF:
    def test_post_without_token_returns_403(self, client):
        r = client.post('/library/new', data={'name': 'X', 'notes': ''})
        assert r.status_code == 403

    def test_post_with_wrong_token_returns_403(self, client):
        _csrf(client)  # puts TEST_TOK in session
        r = client.post('/library/new', data={'csrf_token': 'WRONG', 'name': 'X'})
        assert r.status_code == 403

    def test_post_with_correct_token_passes_csrf(self, client):
        tok = _csrf(client)
        r = client.post('/library/new', data={'csrf_token': tok, 'name': 'CSRF Test'})
        # Either redirect (success) or 200 (re-render with error) — never 403.
        assert r.status_code in (200, 302)

    def test_csrf_via_header(self, client):
        """X-CSRF-Token header is an accepted alternative to form field."""
        tok = _csrf(client)
        r = client.post('/library/new',
                        data={'name': 'Header Test'},
                        headers={'X-CSRF-Token': tok})
        assert r.status_code in (200, 302)

    def test_health_exempt_from_csrf(self, client):
        """Health endpoint is public and not subject to CSRF check."""
        r = client.get('/health')
        assert r.status_code == 200

    def test_csrf_token_in_library_new_form(self, client):
        r = client.get('/library/new')
        assert b'csrf_token' in r.data

    def test_csrf_token_in_wizard_form(self, client):
        r = client.get('/clients/new')
        assert b'csrf_token' in r.data

    def test_csrf_token_in_add_client_form(self, client):
        r = client.get('/clients/add')
        assert b'csrf_token' in r.data


# ---------------------------------------------------------------------------
# Library CRUD
# ---------------------------------------------------------------------------

class TestLibraryCRUD:
    def test_create_program(self, client):
        tok = _csrf(client)
        r = client.post('/library/new', data={
            'csrf_token': tok,
            'name': 'Test Hypertrophy',
            'notes': 'auto-test',
            'session_label': ['Push', 'Pull', 'Legs'],
            'ex_type': ['Push', 'Pull', 'Legs'],
            'ex_name': ['Bench Press', 'Row', 'Squat'],
            'ex_sets': ['4', '4', '4'],
            'ex_reps': ['8', '10', '6'],
            'ex_notes': ['', '', ''],
            'ex_url': ['', '', ''],
        })
        assert r.status_code == 302

    def test_created_program_appears_in_list(self, client):
        r = client.get('/library')
        assert b'Test Hypertrophy' in r.data

    def test_library_json_endpoint(self, client, flask_app):
        import db
        with flask_app.app_context():
            progs = db.list_programs()
        prog = next((p for p in progs if p['name'] == 'Test Hypertrophy'), None)
        assert prog is not None, 'Test Hypertrophy program not found in DB'
        r = client.get(f'/library/{prog["id"]}/json')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['name'] == 'Test Hypertrophy'
        assert len(data['schedule']) == 3
        assert len(data['exercises']) == 3

    def test_json_schedule_has_session_labels(self, client, flask_app):
        import db
        with flask_app.app_context():
            progs = db.list_programs()
        prog = next((p for p in progs if p['name'] == 'Test Hypertrophy'), None)
        r = client.get(f'/library/{prog["id"]}/json')
        data = json.loads(r.data)
        labels = [s['workout_type'] for s in data['schedule']]
        assert labels == ['Push', 'Pull', 'Legs']

    def test_edit_program_get(self, client, flask_app):
        import db
        with flask_app.app_context():
            progs = db.list_programs()
        prog = next((p for p in progs if p['name'] == 'Test Hypertrophy'), None)
        r = client.get(f'/library/{prog["id"]}/edit')
        assert r.status_code == 200
        assert b'Test Hypertrophy' in r.data
        assert b'session-list' in r.data

    def test_edit_program_post(self, client, flask_app):
        import db
        with flask_app.app_context():
            progs = db.list_programs()
        prog = next((p for p in progs if p['name'] == 'Test Hypertrophy'), None)
        tok = _csrf(client)
        r = client.post(f'/library/{prog["id"]}/edit', data={
            'csrf_token': tok,
            'name': 'Test Hypertrophy Updated',
            'notes': '',
            'session_label': ['Push', 'Pull'],
            'ex_type': ['Push'],
            'ex_name': ['Incline Press'],
            'ex_sets': ['3'],
            'ex_reps': ['12'],
            'ex_notes': [''],
            'ex_url': [''],
        })
        assert r.status_code == 302

    def test_delete_program(self, client, flask_app):
        import db
        with flask_app.app_context():
            progs = db.list_programs()
        prog = next((p for p in progs if 'Hypertrophy' in p['name']), None)
        assert prog is not None
        tok = _csrf(client)
        r = client.post(f'/library/{prog["id"]}/delete', data={'csrf_token': tok})
        assert r.status_code == 302
        r2 = client.get('/library')
        assert b'Test Hypertrophy Updated' not in r2.data

    def test_library_json_404_for_missing(self, client):
        r = client.get('/library/99999/json')
        assert r.status_code == 404

    def test_library_edit_404_for_missing(self, client):
        r = client.get('/library/99999/edit')
        assert r.status_code == 404

    def test_library_new_empty_name_returns_200(self, client):
        """Submitting with no name re-renders the form (200), not redirect."""
        tok = _csrf(client)
        r = client.post('/library/new', data={'csrf_token': tok, 'name': '  '})
        assert r.status_code == 200
        assert b'required' in r.data.lower()


# ---------------------------------------------------------------------------
# Wizard step 1 (write_review) — form state round-trip
# ---------------------------------------------------------------------------

class TestWizardReview:
    def test_wizard_write_master_no_name_rerenders(self, client):
        """Submitting write_master with no client name returns 200 (re-renders)."""
        tok = _csrf(client)
        r = client.post('/clients/new', data={
            'csrf_token': tok,
            'action': 'write_master',
            'name': '',          # intentionally blank
            'email': 'test@example.com',
            'program_name': 'PPL',
            'goal': 'Muscle',
            'start_date': '01/07/2026',
            'weight_unit': 'kg',
            'plan_usd': '100',
            'billing_day': '1',
            'num_weeks': '0',
            'calories': '', 'protein': '', 'carbs': '', 'fat': '', 'fiber': '',
        })
        assert r.status_code == 200

    def test_wizard_register_no_name_flashes_error(self, client):
        """register action with no client name returns 200 with error message."""
        tok = _csrf(client)
        r = client.post('/clients/new', data={
            'csrf_token': tok,
            'action': 'register',
            'reg_name': '',
            'reg_sheet': '',
        })
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Error page rendering
# ---------------------------------------------------------------------------

class TestErrorPages:
    def test_404_status(self, client):
        r = client.get('/no-such-route')
        assert r.status_code == 404

    def test_404_page_content(self, client):
        r = client.get('/no-such-route')
        assert b"Not found" in r.data or b"doesn't exist" in r.data

    def test_custom_404_html(self, client):
        r = client.get('/no-such-route')
        assert b'Coach Khader' in r.data
