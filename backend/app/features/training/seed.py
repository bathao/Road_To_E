"""Idempotent column migrations for the Training Center tables.

create_all() never alters existing tables, so columns added after the tables
first shipped are added by hand here (SQLite ADD COLUMN), mirroring the tracker
feature's migrate() idiom. Safe to run on every startup.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

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


def _add_missing_columns(db: Session, table: str, columns: dict[str, str]) -> bool:
    existing = {row[1] for row in db.execute(text(f"PRAGMA table_info({table})"))}
    changed = False
    for name, decl in columns.items():
        if name not in existing:
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))
            changed = True
    return changed


def migrate(db: Session) -> None:
    """Add any columns missing from the Training Center tables. Idempotent."""
    changed = False
    for table, cols in _NEW_COLUMNS.items():
        # PRAGMA on a not-yet-created table returns no rows -> nothing added;
        # create_all (run before seeds) will have made the tables already.
        if _add_missing_columns(db, table, cols):
            changed = True
    if changed:
        db.commit()
