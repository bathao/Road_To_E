"""Idempotent column migrations for the Training Center tables.

create_all() never alters existing tables, so columns added after the tables
first shipped are added by hand (shared helper in app.core.sqlite_migrate).
Safe to run on every startup.
"""
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import add_missing_columns

# table -> {column: SQL type/decl}
_NEW_COLUMNS = {
    "tc_session": {
        "pain": "VARCHAR",       # post-session knee pain: none|mild|strong
        "rpe": "VARCHAR",        # perceived effort: easy|medium|hard
    },
    "tc_session_item": {
        "skipped": "BOOLEAN DEFAULT 0",  # user skipped this exercise (e.g. it hurt)
    },
    "tc_state": {
        "intensity_bias": "INTEGER DEFAULT 0",  # autoregulation: ± overload steps
    },
}


def migrate(db: Session) -> None:
    """Add any columns missing from the Training Center tables. Idempotent."""
    changed = False
    for table, cols in _NEW_COLUMNS.items():
        if add_missing_columns(db, table, cols):
            changed = True
    if changed:
        db.commit()
