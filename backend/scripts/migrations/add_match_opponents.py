"""One-off migration: opponents/partners on matches.

Adds the `tracker_player` table (auto-created by init_db's create_all) and the
new opponent/partner/handicap columns on the existing `tracker_match` table
(create_all does NOT alter existing tables, so we ALTER them here). Idempotent —
safe to re-run.

Run from backend/:

    .venv\\Scripts\\python scripts\\migrations\\add_match_opponents.py
"""
import sys
from pathlib import Path

# Make `app` importable when run as a plain script (sys.path[0] is this dir).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from app.core.db import engine, init_db  # noqa: E402


def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


# column name -> SQL type/clause
_NEW_COLUMNS = {
    "opponent_id": "INTEGER",
    "opponent2_id": "INTEGER",
    "partner_id": "INTEGER",
    "handicap": "INTEGER DEFAULT 0 NOT NULL",
}


def main() -> None:
    # Creates tracker_player (and any other missing tables) from the models.
    init_db()

    with engine.begin() as conn:
        for col, decl in _NEW_COLUMNS.items():
            if _has_column(conn, "tracker_match", col):
                print(f"Column tracker_match.{col} already present.")
                continue
            conn.execute(text(f"ALTER TABLE tracker_match ADD COLUMN {col} {decl}"))
            print(f"Added column tracker_match.{col}.")

    print("Done. tracker_player table ensured; match opponent columns ready.")


if __name__ == "__main__":
    main()
