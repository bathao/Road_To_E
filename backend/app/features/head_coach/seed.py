"""Idempotent column migrations + startup recovery for the Head Coach tables."""
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
    # Background jobs die with the process — un-brick any verdict/chat row a
    # previous run left in flight (local import: service pulls in httpx etc.).
    from app.features.head_coach.service import recover_stuck_jobs

    recover_stuck_jobs(db)
