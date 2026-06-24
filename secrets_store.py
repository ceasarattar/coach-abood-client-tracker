"""
Encrypted store for sensitive per-client secrets (Cronometer logins).

Passwords NEVER go in the client registry, the Google Sheet, or git in plain
text. They are encrypted with Fernet (AES) and the ciphertext is kept in the
shared database (app_kv table), so a single hosted instance has them too.

Key management:
  * Production: set the Fernet key in the CRONOMETER_KEY environment variable
    (generate one with `python -c "from cryptography.fernet import Fernet;
    print(Fernet.generate_key().decode())"`). It is never stored in the DB.
  * Local dev: if CRONOMETER_KEY is unset, a key is generated once and kept in
    the DB (app_kv) so the encrypt/decrypt round-trips on this machine.

This is encryption at rest. It protects the ciphertext if the DB is copied; it
is not a substitute for account-level security.
"""
import os
import json

from cryptography.fernet import Fernet

import db

_KV_KEY_CREDS = "cronometer_creds"     # encrypted JSON blob of {name: {email,password}}
_KV_KEY_FERNET = "cronometer_fernet_key"  # dev-only fallback key storage


def _fernet() -> Fernet:
    key = os.environ.get("CRONOMETER_KEY", "").strip()
    if key:
        return Fernet(key.encode())
    # Dev fallback: persist a generated key in the DB so it survives restarts.
    stored = db.kv_get(_KV_KEY_FERNET)
    if not stored:
        stored = Fernet.generate_key().decode()
        db.kv_set(_KV_KEY_FERNET, stored)
    return Fernet(stored.encode())


def _read_all() -> dict:
    blob = db.kv_get(_KV_KEY_CREDS)
    if not blob:
        return {}
    try:
        raw = _fernet().decrypt(blob.encode())
        return json.loads(raw.decode("utf-8"))
    except Exception:
        # A changed/rotated key can't decrypt old data — treat as empty rather
        # than crash; the coach can re-enter the affected client's login.
        return {}


def _write_all(data: dict) -> None:
    blob = _fernet().encrypt(json.dumps(data).encode("utf-8")).decode("ascii")
    db.kv_set(_KV_KEY_CREDS, blob)


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


def rename_credentials(old_name: str, new_name: str) -> bool:
    """Move a client's stored creds from old_name to new_name. Returns True if
    moved. Keeps Cronometer logins attached when a client is renamed (otherwise
    they would be orphaned, since creds are keyed by name)."""
    data = _read_all()
    old_key = old_name.strip().lower()
    if old_key not in data:
        return False
    data[new_name.strip().lower()] = data.pop(old_key)
    _write_all(data)
    return True
