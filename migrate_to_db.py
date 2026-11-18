"""Copy local data (state/*.json and state/users.db) into the database named by DATABASE_URL.

Usage:  set DATABASE_URL in .env (or the environment), then run
        python migrate_to_db.py

Safe to run more than once: anything already in the database is left untouched.
"""

from __future__ import annotations

import os
import sys

import db
import interview  # noqa: F401  (loads .env)


def main() -> None:
    if not os.getenv("DATABASE_URL", "").strip():
        sys.exit("DATABASE_URL is not set, so there is nothing to migrate to.")
    eng = db.engine()
    counts = db.import_legacy(eng)
    print(
        f"Imported {counts['applications']} application(s), {counts['users']} user(s) and "
        f"{counts['progress']} progress record(s) into {eng.url.render_as_string(hide_password=True)}"
    )


if __name__ == "__main__":
    main()
