"""
Seed (or re-seed) the local workout library from seed/programs.json.

Idempotent: a program whose name already exists is replaced, not duplicated.
Run automatically by setup, or manually any time:

    python scripts/seed_library.py
"""
import json
import os
import sys

# Make the project root importable regardless of where this is run from.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

import db  # noqa: E402

SEED_PATH = os.path.join(_ROOT, "seed", "programs.json")


def main() -> int:
    db.init_db()
    if not os.path.exists(SEED_PATH):
        print(f"No seed file at {SEED_PATH} — nothing to load.")
        return 0

    with open(SEED_PATH, encoding="utf-8") as fh:
        programs = json.load(fh)

    for p in programs:
        existing = db.get_program_by_name(p["name"])
        if existing:
            db.delete_program(existing["id"])
        db.create_program(p)
        training = sum(1 for s in p["schedule"] if s["workout_type"] != "Rest")
        print(f"  seeded '{p['name']}': {training} training days, "
              f"{len(p['exercises'])} exercises")

    print(f"Library seeded from {os.path.relpath(SEED_PATH, _ROOT)} "
          f"({len(programs)} programs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
