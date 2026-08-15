"""Tactics feature seed: startup recovery (tables are new — no migrations)."""
from sqlalchemy.orm import Session


def migrate(db: Session) -> None:
    # Local import: service pulls in httpx etc. (same pattern as head_coach).
    from app.features.tactics.service import recover_stuck_plans

    recover_stuck_plans(db)
