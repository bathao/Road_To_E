"""Shared idempotent SQLite column migrations.

create_all() never alters existing tables, so columns added after a table first
shipped are added by hand (SQLite ADD COLUMN). Every feature seed uses this one
helper instead of keeping its own copy. Safe to run on every startup.
"""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def table_columns(db: Session, table: str) -> set[str]:
    """Column names of *table* ({} when the table doesn't exist yet)."""
    return {row[1] for row in db.execute(text(f"PRAGMA table_info({table})"))}


def add_missing_columns(db: Session, table: str, columns: dict[str, str]) -> bool:
    """ALTER TABLE ADD COLUMN for each column missing from *table*.

    Returns True when something was added. A not-yet-created table is left
    untouched (create_all, which runs before the seeds, will make it whole).
    """
    existing = table_columns(db, table)
    if not existing:
        return False
    changed = False
    for name, decl in columns.items():
        if name not in existing:
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))
            log.info("migrate: added column %s.%s (%s)", table, name, decl)
            changed = True
    return changed
