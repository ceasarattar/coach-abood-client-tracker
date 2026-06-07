"""
SQLite layer for the Coach Abood dashboard's local workout library.

Stores reusable workout PROGRAMS only (schedule + exercises). No client data
ever lives here — that belongs in Google Sheets. The schema is created from
schema.sql (run by setup scripts or lazily via init_db()).

A "program" round-trips as a single dict:
    {
        "id": int | None,
        "name": str,
        "notes": str,
        "schedule": [{"day_order": int, "day_name": str, "workout_type": str}, ...],
        "exercises": [
            {"workout_type": str, "position": int, "exercise": str,
             "target_sets": str, "target_reps": str,
             "coach_notes": str, "tutorial_url": str}, ...
        ],
    }
"""
import os
import sqlite3
from typing import Any, Optional

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "coach_data.db")
SCHEMA_PATH = os.path.join(_BASE_DIR, "schema.sql")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"]
# Suggestions only — the UI accepts any free-text day type. These populate a
# datalist for convenience; coaches can type anything (e.g. "Arms", "Conditioning").
WORKOUT_TYPES = ["Push", "Pull", "Legs", "Upper", "Lower", "Full Body",
                 "Chest", "Back", "Shoulders", "Arms", "Core",
                 "Cardio", "Conditioning", "Rest"]


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with row access by name and FKs enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH, schema_path: str = SCHEMA_PATH) -> None:
    """Create tables from schema.sql if they do not already exist."""
    with open(schema_path) as fh:
        schema_sql = fh.read()
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_programs(db_path: str = DB_PATH) -> list[dict[str, Any]]:
    """Return all programs as lightweight summaries (no nested data)."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.name, p.notes, p.updated_at,
                   (SELECT COUNT(*) FROM program_exercises e
                    WHERE e.program_id = p.id) AS exercise_count,
                   (SELECT COUNT(*) FROM program_schedule s
                    WHERE s.program_id = p.id
                      AND s.workout_type != 'Rest') AS training_days
            FROM programs p
            ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_program(program_id: int, db_path: str = DB_PATH) -> Optional[dict[str, Any]]:
    """Return one fully-populated program dict, or None if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM programs WHERE id = ?", (program_id,)
        ).fetchone()
        if row is None:
            return None
        program = dict(row)
        program["schedule"] = [
            dict(r) for r in conn.execute(
                """SELECT day_order, day_name, workout_type
                   FROM program_schedule WHERE program_id = ?
                   ORDER BY day_order""",
                (program_id,),
            ).fetchall()
        ]
        program["exercises"] = [
            dict(r) for r in conn.execute(
                """SELECT workout_type, position, exercise, target_sets,
                          target_reps, coach_notes, tutorial_url
                   FROM program_exercises WHERE program_id = ?
                   ORDER BY position, id""",
                (program_id,),
            ).fetchall()
        ]
        return program
    finally:
        conn.close()


def get_program_by_name(name: str, db_path: str = DB_PATH) -> Optional[dict[str, Any]]:
    """Look up a program id by name then return the full dict, or None."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM programs WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
    finally:
        conn.close()
    return get_program(row["id"], db_path) if row else None


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def _replace_children(conn: sqlite3.Connection, program_id: int,
                      schedule: list[dict[str, Any]],
                      exercises: list[dict[str, Any]]) -> None:
    """Delete + reinsert schedule and exercises for a program (used by create/update)."""
    conn.execute("DELETE FROM program_schedule WHERE program_id = ?", (program_id,))
    conn.execute("DELETE FROM program_exercises WHERE program_id = ?", (program_id,))

    for s in schedule:
        conn.execute(
            """INSERT INTO program_schedule
                   (program_id, day_order, day_name, workout_type)
               VALUES (?, ?, ?, ?)""",
            (program_id, int(s.get("day_order", 0)),
             s.get("day_name", ""), s.get("workout_type", "Rest")),
        )
    for i, e in enumerate(exercises):
        conn.execute(
            """INSERT INTO program_exercises
                   (program_id, workout_type, position, exercise,
                    target_sets, target_reps, coach_notes, tutorial_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (program_id, e.get("workout_type", ""), int(e.get("position", i)),
             e.get("exercise", ""), str(e.get("target_sets", "")),
             str(e.get("target_reps", "")), e.get("coach_notes", ""),
             e.get("tutorial_url", "")),
        )


def create_program(program: dict[str, Any], db_path: str = DB_PATH) -> int:
    """Insert a new program (with schedule + exercises). Returns the new id."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO programs (name, notes) VALUES (?, ?)",
            (program["name"], program.get("notes", "")),
        )
        program_id = cur.lastrowid
        _replace_children(conn, program_id,
                         program.get("schedule", []),
                         program.get("exercises", []))
        conn.commit()
        return program_id
    finally:
        conn.close()


def update_program(program_id: int, program: dict[str, Any],
                   db_path: str = DB_PATH) -> bool:
    """Update an existing program in place. Returns False if id not found."""
    conn = get_connection(db_path)
    try:
        exists = conn.execute(
            "SELECT 1 FROM programs WHERE id = ?", (program_id,)
        ).fetchone()
        if not exists:
            return False
        conn.execute(
            """UPDATE programs
               SET name = ?, notes = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (program["name"], program.get("notes", ""), program_id),
        )
        _replace_children(conn, program_id,
                         program.get("schedule", []),
                         program.get("exercises", []))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_program(program_id: int, db_path: str = DB_PATH) -> bool:
    """Delete a program and its children (cascade). Returns rows-deleted bool."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM programs WHERE id = ?", (program_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialised database at {DB_PATH}")
