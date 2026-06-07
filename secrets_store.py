"""
Encrypted local store for sensitive per-client secrets (Cronometer logins).

Passwords NEVER go in clients.yaml, the Google Sheet, the database, or git.
They live only in `cronometer_creds.enc`, encrypted with a key in
`cronometer.key`. Both files are gitignored and stay on the coach's machine.

This is symmetric encryption at rest (Fernet/AES). It protects the file if it's
copied off the machine; it is not a substitute for OS-level account security.
"""
import os
import json

from cryptography.fernet import Fernet

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(_BASE_DIR, "cronometer.key")
STORE_PATH = os.path.join(_BASE_DIR, "cronometer_creds.enc")


def _load_key() -> bytes:
    """Return the Fernet key, creating it on first use (chmod 600)."""
    if not os.path.exists(KEY_PATH):
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as fh:
            fh.write(key)
        try:
            os.chmod(KEY_PATH, 0o600)
        except OSError:
            pass  # Windows / unsupported FS — best effort.
        return key
    with open(KEY_PATH, "rb") as fh:
        return fh.read()


def _read_all() -> dict:
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH, "rb") as fh:
        blob = fh.read()
    if not blob:
        return {}
    raw = Fernet(_load_key()).decrypt(blob)
    return json.loads(raw.decode("utf-8"))


def _write_all(data: dict) -> None:
    blob = Fernet(_load_key()).encrypt(json.dumps(data).encode("utf-8"))
    with open(STORE_PATH, "wb") as fh:
        fh.write(blob)
    try:
        os.chmod(STORE_PATH, 0o600)
    except OSError:
        pass


def set_credentials(client_name: str, email: str, password: str) -> None:
    """Store (encrypted) Cronometer credentials for a client, keyed by name."""
    data = _read_all()
    data[client_name.strip().lower()] = {"email": email, "password": password}
    _write_all(data)


def get_credentials(client_name: str):
    """Return {'email','password'} for a client, or None if not stored."""
    return _read_all().get(client_name.strip().lower())


def has_credentials(client_name: str) -> bool:
    return client_name.strip().lower() in _read_all()


def delete_credentials(client_name: str) -> bool:
    data = _read_all()
    if client_name.strip().lower() in data:
        del data[client_name.strip().lower()]
        _write_all(data)
        return True
    return False
