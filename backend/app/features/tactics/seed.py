"""Tactics feature seed: column migrations + startup recovery."""
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import add_missing_columns

_FACT_COLUMNS = {
    # Canonical intake slot (2026-08-17 structured-intake rework). Existing
    # free-form facts stay key-less.
    "key": "VARCHAR",
}


def migrate(db: Session) -> None:
    # Local import: service pulls in httpx etc. (same pattern as head_coach).
    from app.features.tactics.service import recover_stuck_plans

    if add_missing_columns(db, "tactic_fact", _FACT_COLUMNS):
        db.commit()
    recover_stuck_plans(db)
