"""Pytest fixtures for the Coach Khader dashboard test suite."""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure the coach_dashboard package root is on the path.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Use an in-memory SQLite database so tests never touch the dev DB.
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
# Disable the passcode gate so all routes are reachable without auth.
os.environ.pop('WEBAPP_PASSCODE', None)
# Prevent any outbound Sheets/Apps Script calls in unit tests.
os.environ.pop('TEMPLATE_WEBAPP_URL', None)
os.environ.pop('GOOGLE_SERVICE_ACCOUNT_JSON', None)


@pytest.fixture(scope='session')
def flask_app():
    """Application fixture — uses in-memory SQLite and creates all tables."""
    import app as flask_app_module
    import db
    flask_app_module.app.config.update(
        TESTING=True,
        SECRET_KEY='test-secret-key-not-used-in-prod',
    )
    # Create tables in the in-memory DB.
    with flask_app_module.app.app_context():
        db.init_db()
    yield flask_app_module.app


@pytest.fixture
def client(flask_app):
    """A test client with a fresh session per test."""
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def authed_client(flask_app):
    """Test client with a CSRF token already in the session."""
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess['csrf_token'] = 'TEST_TOKEN'
        yield c


@pytest.fixture
def csrf_data():
    """Helper: returns a dict with the test CSRF token."""
    return {'csrf_token': 'TEST_TOKEN'}


def _make_form(**kwargs):
    """Build an ImmutableMultiDict suitable for passing to Flask view functions.

    Supports multi-valued keys: pass a list as the value and each element
    becomes a separate form entry under the same key.
    """
    from werkzeug.datastructures import ImmutableMultiDict

    parts = []
    for k, v in kwargs.items():
        if isinstance(v, (list, tuple)):
            for item in v:
                parts.append((k, str(item)))
        else:
            parts.append((k, str(v) if v is not None else ''))
    return ImmutableMultiDict(parts)
