"""One-off migration: add Activity.is_package_start and backfill 'N' markers.

Coaching is bought in 10-session packages. The first session of a package used
to be flagged by typing 'N' into that day's Train-with-Coach note. This migrates
that convention to a real boolean column. Idempotent — safe to re-run.

Run from backend/:

    .venv\\Scripts\\python scripts\\migrations\\add_coach_package_marker.py
"""
import sys
from pathlib import Path

# Make `app` importable when run as a plain script (sys.path[0] is this dir).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal, engine, init_db  # noqa: E402
from app.features.tracker.models import Activity, Category  # noqa: E402


def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def main() -> None:
    init_db()

    # 1. Add the column if missing (SQLite has no IF NOT EXISTS for columns).
    with engine.begin() as conn:
        if not _has_column(conn, "tracker_activity", "is_package_start"):
            conn.execute(
                text(
                    "ALTER TABLE tracker_activity "
                    "ADD COLUMN is_package_start BOOLEAN DEFAULT 0 NOT NULL"
                )
            )
            print("Added column tracker_activity.is_package_start.")
        else:
            print("Column tracker_activity.is_package_start already present.")

    # 2. Backfill: 'N'-noted coach sessions become package starts.
    db = SessionLocal()
    try:
        coach = db.query(Category).filter(Category.key == "train_with_coach").first()
        if coach is None:
            print("No train_with_coach category — nothing to backfill.")
            return
        marked = 0
        rows = (
            db.query(Activity)
            .filter(Activity.category_id == coach.id, Activity.note == "N")
            .all()
        )
        for a in rows:
            a.is_package_start = True
            a.note = None
            marked += 1
        db.commit()
        print(f"Backfilled {marked} package-start marker(s) from 'N' notes.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
