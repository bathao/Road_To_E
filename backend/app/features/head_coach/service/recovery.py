"""Startup recovery of rows left in flight by a previous process.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.features.head_coach.models import (
    CoachChatMessage,
    HeadCoachAssessment,
    HeadCoachRecap,
)
from app.shared.jobs import recover_stuck


def recover_stuck_jobs(db: Session) -> None:
    """Mark rows orphaned by a crash/restart as errors (run at startup).

    Background jobs die with the process. A verdict left `generating` keeps
    the GUI's Generate button disabled forever, and a chat reply left
    `pending` blocks the chat input AND every new POST /chat (409) — with no
    job alive to ever finish them. Flip them to a visible error instead."""
    n = recover_stuck(db, HeadCoachAssessment, in_flight="generating", label="assessment(s)")
    n += recover_stuck(db, CoachChatMessage, in_flight="pending", label="chat row(s)")
    n += recover_stuck(db, HeadCoachRecap, in_flight="generating", label="recap(s)")
    if n:
        db.commit()
