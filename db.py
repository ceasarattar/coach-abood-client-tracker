"""
Shared database layer for the Coach Abood dashboard.

Runs on **SQLite locally** and **Postgres in production** (Neon/Render) — the
backend is chosen by the DATABASE_URL environment variable:

    (unset)                       -> sqlite:///coach_data.db   (local dev)
    postgres://… / postgresql://… -> normalised to postgresql+psycopg://…

What lives here (all shared, so a hosted instance is the single source of truth):
  * the reusable workout PROGRAM library (schedule + exercises),
  * the client registry (name + Google Sheet id + plan), formerly clients.yaml,
  * a tiny key/value table (app_kv) used for encrypted Cronometer creds.

Client LOGS still live in Google Sheets — never here.

A "program" round-trips as a single dict:
    {
        "id": int | None, "name": str, "notes": str,
        "schedule":  [{"day_order": int, "day_name": str, "workout_type": str}, ...],
        "exercises": [{"workout_type": str, "position": int, "exercise": str,
                       "target_sets": str, "target_reps": str,
                       "coach_notes": str, "tutorial_url": str}, ...],
    }

A "client" round-trips as:
    {"name", "spreadsheet_id", "master_spreadsheet_id", "plan_usd",
     "weight_unit", "active"}
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, String,
                        Text, Boolean, Float, func, select, insert, update,
                        delete as sa_delete)

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "coach_data.db")          # local SQLite default
SCHEMA_PATH = os.path.join(_BASE_DIR, "schema.sql")          # kept for reference
SEED_PATH = os.path.join(_BASE_DIR, "seed", "programs.json")
LEGACY_CLIENTS_YAML = os.path.join(_BASE_DIR, "clients.yaml")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"]
# Suggestions only — the UI accepts any free-text day type. These populate a
# datalist for convenience; coaches can type anything (e.g. "Arms", "Conditioning").
WORKOUT_TYPES = ["Push", "Pull", "Legs", "Upper", "Lower", "Full Body",
                 "Chest", "Back", "Shoulders", "Arms", "Core",
                 "Cardio", "Conditioning", "Rest"]


# ---------------------------------------------------------------------------
# Engine + schema
# ---------------------------------------------------------------------------

def _database_url() -> str:
    """Resolve the SQLAlchemy URL from DATABASE_URL, defaulting to local SQLite."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{DB_PATH}"
    # Normalise the common provider prefixes to the psycopg3 driver.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _make_engine():
    url = _database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, future=True,
                        connect_args=connect_args)


engine = _make_engine()
metadata = MetaData()

programs = Table(
    "programs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False, unique=True),
    Column("notes", Text, default=""),
    Column("created_at", String(32), default=lambda: _now()),
    Column("updated_at", String(32), default=lambda: _now(), onupdate=lambda: _now()),
)

program_schedule = Table(
    "program_schedule", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("program_id", Integer, nullable=False, index=True),
    Column("day_order", Integer, nullable=False),
    Column("day_name", String(32), nullable=False),
    Column("workout_type", String(64), nullable=False, default="Rest"),
)

program_exercises = Table(
    "program_exercises", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("program_id", Integer, nullable=False, index=True),
    Column("workout_type", String(64), nullable=False),
    Column("position", Integer, nullable=False, default=0),
    Column("exercise", Text, nullable=False),
    Column("target_sets", Text, default=""),
    Column("target_reps", Text, default=""),
    Column("coach_notes", Text, default=""),
    Column("tutorial_url", Text, default=""),
)

clients = Table(
    "clients", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False, unique=True),
    Column("spreadsheet_id", String(255), nullable=False, default=""),
    Column("master_spreadsheet_id", String(255), default=""),
    Column("plan_usd", Float, default=0),
    Column("weight_unit", String(8), default="kg"),
    Column("active", Boolean, default=True),
    Column("position", Integer, default=0),
)

# Tiny key/value store for small encrypted blobs (Cronometer creds, fernet key).
app_kv = Table(
    "app_kv", metadata,
    Column("key", String(64), primary_key=True),
    Column("value", Text),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    """Create all tables if they do not already exist. Idempotent."""
    metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Programs — read
# ---------------------------------------------------------------------------

def list_programs() -> list[dict[str, Any]]:
    """Return all programs as lightweight summaries (no nested data)."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(programs.c.id, programs.c.name, programs.c.notes,
                   programs.c.updated_at).order_by(func.lower(programs.c.name))
        ).all()

        ex_counts = dict(conn.execute(
            select(program_exercises.c.program_id,
                   func.count().label("n")).group_by(program_exercises.c.program_id)
        ).all())
        day_counts = dict(conn.execute(
            select(program_schedule.c.program_id, func.count().label("n"))
            .where(program_schedule.c.workout_type != "Rest")
            .group_by(program_schedule.c.program_id)
        ).all())

    out = []
    for r in rows:
        out.append({
            "id": r.id, "name": r.name, "notes": r.notes, "updated_at": r.updated_at,
            "exercise_count": ex_counts.get(r.id, 0),
            "training_days": day_counts.get(r.id, 0),
        })
    return out


def get_program(program_id: int) -> Optional[dict[str, Any]]:
    """Return one fully-populated program dict, or None if not found."""
    with engine.connect() as conn:
        row = conn.execute(
            select(programs).where(programs.c.id == program_id)
        ).mappings().first()
        if row is None:
            return None
        program = dict(row)
        program["schedule"] = [dict(r) for r in conn.execute(
            select(program_schedule.c.day_order, program_schedule.c.day_name,
                   program_schedule.c.workout_type)
            .where(program_schedule.c.program_id == program_id)
            .order_by(program_schedule.c.day_order)
        ).mappings().all()]
        program["exercises"] = [dict(r) for r in conn.execute(
            select(program_exercises.c.workout_type, program_exercises.c.position,
                   program_exercises.c.exercise, program_exercises.c.target_sets,
                   program_exercises.c.target_reps, program_exercises.c.coach_notes,
                   program_exercises.c.tutorial_url)
            .where(program_exercises.c.program_id == program_id)
            .order_by(program_exercises.c.position, program_exercises.c.id)
        ).mappings().all()]
        return program


def get_program_by_name(name: str) -> Optional[dict[str, Any]]:
    """Look up a program id by name (case-insensitive) then return the full dict."""
    with engine.connect() as conn:
        row = conn.execute(
            select(programs.c.id).where(func.lower(programs.c.name) == name.lower())
        ).first()
    return get_program(row.id) if row else None


# ---------------------------------------------------------------------------
# Programs — write
# ---------------------------------------------------------------------------

def _replace_children(conn, program_id: int,
                      schedule: list[dict[str, Any]],
                      exercises: list[dict[str, Any]]) -> None:
    """Delete + reinsert schedule and exercises for a program."""
    conn.execute(sa_delete(program_schedule)
                 .where(program_schedule.c.program_id == program_id))
    conn.execute(sa_delete(program_exercises)
                 .where(program_exercises.c.program_id == program_id))

    for s in schedule:
        conn.execute(insert(program_schedule).values(
            program_id=program_id, day_order=int(s.get("day_order", 0)),
            day_name=s.get("day_name", ""),
            workout_type=s.get("workout_type", "Rest")))
    for i, e in enumerate(exercises):
        conn.execute(insert(program_exercises).values(
            program_id=program_id, workout_type=e.get("workout_type", ""),
            position=int(e.get("position", i)), exercise=e.get("exercise", ""),
            target_sets=str(e.get("target_sets", "")),
            target_reps=str(e.get("target_reps", "")),
            coach_notes=e.get("coach_notes", ""),
            tutorial_url=e.get("tutorial_url", "")))


def create_program(program: dict[str, Any]) -> int:
    """Insert a new program (with schedule + exercises). Returns the new id."""
    with engine.begin() as conn:
        result = conn.execute(insert(programs).values(
            name=program["name"], notes=program.get("notes", ""),
            created_at=_now(), updated_at=_now()))
        program_id = result.inserted_primary_key[0]
        _replace_children(conn, program_id,
                          program.get("schedule", []), program.get("exercises", []))
        return program_id


def update_program(program_id: int, program: dict[str, Any]) -> bool:
    """Update an existing program in place. Returns False if id not found."""
    with engine.begin() as conn:
        exists = conn.execute(
            select(programs.c.id).where(programs.c.id == program_id)).first()
        if not exists:
            return False
        conn.execute(update(programs).where(programs.c.id == program_id).values(
            name=program["name"], notes=program.get("notes", ""), updated_at=_now()))
        _replace_children(conn, program_id,
                          program.get("schedule", []), program.get("exercises", []))
        return True


def delete_program(program_id: int) -> bool:
    """Delete a program and its children. Returns True if a row was removed."""
    with engine.begin() as conn:
        conn.execute(sa_delete(program_schedule)
                     .where(program_schedule.c.program_id == program_id))
        conn.execute(sa_delete(program_exercises)
                     .where(program_exercises.c.program_id == program_id))
        result = conn.execute(sa_delete(programs).where(programs.c.id == program_id))
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# Clients (registry that used to live in clients.yaml)
# ---------------------------------------------------------------------------

def _client_dict(row) -> dict[str, Any]:
    return {
        "name": row.name, "spreadsheet_id": row.spreadsheet_id,
        "master_spreadsheet_id": row.master_spreadsheet_id or "",
        "plan_usd": row.plan_usd, "weight_unit": row.weight_unit or "kg",
        "active": bool(row.active),
    }


def list_clients(active_only: bool = False) -> list[dict[str, Any]]:
    """Return the client registry (same shape the app used from clients.yaml)."""
    with engine.connect() as conn:
        stmt = select(clients).order_by(clients.c.position, clients.c.id)
        if active_only:
            stmt = stmt.where(clients.c.active == True)  # noqa: E712
        return [_client_dict(r) for r in conn.execute(stmt).all()]


def get_client_by_name(name: str) -> Optional[dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(
            select(clients).where(func.lower(clients.c.name) == name.strip().lower())
        ).first()
    return _client_dict(row) if row else None


def client_exists(name: str) -> bool:
    return get_client_by_name(name) is not None


def add_client(client: dict[str, Any]) -> None:
    """Insert a new client. Caller should check client_exists() first."""
    with engine.begin() as conn:
        maxpos = conn.execute(select(func.max(clients.c.position))).scalar() or 0
        conn.execute(insert(clients).values(
            name=client["name"], spreadsheet_id=client.get("spreadsheet_id", ""),
            master_spreadsheet_id=client.get("master_spreadsheet_id", ""),
            plan_usd=_as_float(client.get("plan_usd"), 0),
            weight_unit=client.get("weight_unit", "kg"),
            active=bool(client.get("active", True)), position=maxpos + 1))


def update_client(old_name: str, fields: dict[str, Any]) -> bool:
    """
    Update a client row, located by its current name. Returns False if not found.

    Only the keys present in `fields` are changed. The caller is responsible for
    re-keying name-scoped external data (Cronometer creds, nutrition cache) when
    the name changes — see app._rename_client_artifacts. This separation is
    deliberate: db.py never reaches into secrets_store/cache.
    """
    with engine.begin() as conn:
        row = conn.execute(select(clients.c.id).where(
            func.lower(clients.c.name) == old_name.strip().lower())).first()
        if not row:
            return False
        values: dict[str, Any] = {}
        if "name" in fields:
            values["name"] = str(fields["name"]).strip()
        if "spreadsheet_id" in fields:
            values["spreadsheet_id"] = str(fields["spreadsheet_id"]).strip()
        if "master_spreadsheet_id" in fields:
            values["master_spreadsheet_id"] = str(fields.get("master_spreadsheet_id") or "").strip()
        if "plan_usd" in fields:
            values["plan_usd"] = _as_float(fields["plan_usd"], 0)
        if "weight_unit" in fields:
            values["weight_unit"] = (fields.get("weight_unit") or "kg")
        if "active" in fields:
            values["active"] = bool(fields["active"])
        if values:
            conn.execute(update(clients).where(clients.c.id == row.id).values(**values))
        return True


def delete_client(name: str) -> bool:
    """
    Hard-delete a client row by name. Returns True if a row was removed.

    Unregister-only: this removes the dashboard's record. Name-scoped external
    data (creds, caches) is purged by the caller; the client's Google Sheet in
    Drive is intentionally left untouched.
    """
    with engine.begin() as conn:
        result = conn.execute(sa_delete(clients).where(
            func.lower(clients.c.name) == name.strip().lower()))
        return result.rowcount > 0


def set_client_active(name: str, active: bool) -> bool:
    """Toggle a client's active flag (deactivated clients hide from the main
    list but keep their row so they can be restored). Returns True if updated."""
    with engine.begin() as conn:
        result = conn.execute(update(clients).where(
            func.lower(clients.c.name) == name.strip().lower()
        ).values(active=bool(active)))
        return result.rowcount > 0


def _as_float(value, default=0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError, AttributeError):
        return default


# ---------------------------------------------------------------------------
# Key/value store (used by secrets_store for encrypted Cronometer creds)
# ---------------------------------------------------------------------------

def kv_get(key: str) -> Optional[str]:
    with engine.connect() as conn:
        row = conn.execute(select(app_kv.c.value).where(app_kv.c.key == key)).first()
    return row.value if row else None


def kv_set(key: str, value: str) -> None:
    with engine.begin() as conn:
        exists = conn.execute(select(app_kv.c.key).where(app_kv.c.key == key)).first()
        if exists:
            conn.execute(update(app_kv).where(app_kv.c.key == key).values(value=value))
        else:
            conn.execute(insert(app_kv).values(key=key, value=value))


def kv_delete(key: str) -> None:
    """Remove a key/value entry (used to purge a deleted client's caches)."""
    with engine.begin() as conn:
        conn.execute(sa_delete(app_kv).where(app_kv.c.key == key))


# ---------------------------------------------------------------------------
# First-boot bootstrap: create tables, seed the library, import legacy clients
# ---------------------------------------------------------------------------

def bootstrap() -> None:
    """
    Make a fresh database usable with zero manual steps. Safe to call on every
    process start: each step is guarded so it only acts when needed.
      1. create tables,
      2. seed the workout library from seed/programs.json if it is empty,
      3. import clients.yaml if the clients table is empty and the file exists.
    """
    init_db()
    try:
        _seed_library_if_empty()
    except Exception as exc:  # never let seeding crash startup
        logger.warning("Library seed skipped: %s", exc)
    try:
        _import_clients_if_empty()
    except Exception as exc:
        logger.warning("Client import skipped: %s", exc)


def _seed_library_if_empty() -> None:
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(programs)).scalar()
    if count or not os.path.exists(SEED_PATH):
        return
    with open(SEED_PATH, encoding="utf-8") as fh:
        seeded = json.load(fh)
    for p in seeded:
        create_program(p)
    logger.info("Seeded workout library: %d programs", len(seeded))


def _import_clients_if_empty() -> None:
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(clients)).scalar()
    if count or not os.path.exists(LEGACY_CLIENTS_YAML):
        return
    import yaml  # local import — only needed for the one-time migration
    with open(LEGACY_CLIENTS_YAML) as fh:
        data = yaml.safe_load(fh) or {}
    for c in data.get("clients", []):
        if c.get("name") and not client_exists(c["name"]):
            add_client(c)
    logger.info("Imported %d clients from clients.yaml", len(data.get("clients", [])))


if __name__ == "__main__":
    bootstrap()
    print(f"Database ready at {_database_url()}")
    print(f"  programs: {len(list_programs())}   clients: {len(list_clients())}")
