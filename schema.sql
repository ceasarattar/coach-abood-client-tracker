-- Coach Abood Dashboard — SQLite schema for the local workout library.
--
-- Stores reusable workout PROGRAMS only. All client data lives in Google
-- Sheets; this database never holds client logs. Run by setup.sh / setup.bat.
--
-- A program has:
--   * a name (e.g. "PPL Hypertrophy")
--   * a weekly schedule: day -> workout type (Push/Pull/Legs/Upper/Lower/Rest)
--   * exercises grouped by workout type, each with sets/reps/notes/tutorial
--
-- Mirrors the master sheet's "Program Builder" tab so a program can be written
-- straight into the admin tabs during client setup.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS programs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    notes       TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Weekly schedule rows: one per day of the week (or as many as defined).
CREATE TABLE IF NOT EXISTS program_schedule (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id    INTEGER NOT NULL,
    day_order     INTEGER NOT NULL,   -- 1..7 (Mon..Sun)
    day_name      TEXT    NOT NULL,   -- "Monday" etc.
    workout_type  TEXT    NOT NULL DEFAULT 'Rest',  -- Push/Pull/Legs/Upper/Lower/Rest
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE
);

-- Exercises grouped by workout type within a program.
CREATE TABLE IF NOT EXISTS program_exercises (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id    INTEGER NOT NULL,
    workout_type  TEXT    NOT NULL,         -- Push/Pull/Legs/Upper/Lower
    position      INTEGER NOT NULL DEFAULT 0,  -- order within the workout type
    exercise      TEXT    NOT NULL,
    target_sets   TEXT    DEFAULT '',       -- text: matches sheet (e.g. "2")
    target_reps   TEXT    DEFAULT '',       -- text: e.g. "8, 6"
    coach_notes   TEXT    DEFAULT '',
    tutorial_url  TEXT    DEFAULT '',
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_schedule_program  ON program_schedule(program_id);
CREATE INDEX IF NOT EXISTS idx_exercises_program ON program_exercises(program_id);
