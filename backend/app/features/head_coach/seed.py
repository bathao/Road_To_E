"""Idempotent column migrations for the Head Coach table."""
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import add_missing_columns

# Existing rows are completed verdicts → they default to 'done'.
_ASSESSMENT_COLUMNS = {
    "status": "VARCHAR DEFAULT 'done'",
    "error_msg": "TEXT",
}


def migrate(db: Session) -> None:
    if add_missing_columns(db, "hc_assessment", _ASSESSMENT_COLUMNS):
        db.commit()
