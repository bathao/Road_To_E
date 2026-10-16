"""The lifecycle every background LLM job shares.

A job row (verdict, recap, chat reply, tactic plan) is created in an
in-flight status by the request handler, then filled by a background task:

    fetch row → still in flight? → work(db, row) → commit
                                 ↘ any failure → rollback, row.status = "error",
                                                 row.error_msg = str(exc)

The failure branch is what keeps the GUI usable: a row left in flight with no
job alive blocks its button (and, for chat, every new message) until a
restart. ``recover_stuck`` handles the restart case itself.

Jobs accept an injected session so tests run them synchronously; without one
they open and close their own ``SessionLocal``.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.db import SessionLocal

log = logging.getLogger(__name__)

# What a stuck row says after a restart (Vietnamese: it is shown in the GUI).
STUCK_MSG = "Server restarted trong lúc đang chạy — bấm chạy lại."
# error_msg columns are plain TEXT; keep tracebacks' str() bounded anyway.
ERROR_MSG_MAX = 1000


def run_llm_job(
    db_or_none: Session | None,
    *,
    fetch: Callable[[Session], Any],
    work: Callable[[Session, Any], None],
    tag: str,
    in_flight: str = "generating",
) -> None:
    """Run one job: ``fetch`` returns the row (or None), ``work`` fills it.

    ``work`` may commit itself; the helper commits after it returns so a
    job that only sets fields is enough. On any exception the row is
    re-fetched on the rolled-back session and marked ``error``."""
    db = db_or_none or SessionLocal()
    try:
        row = fetch(db)
        if row is None or row.status != in_flight:
            return
        try:
            work(db, row)
            db.commit()
        except Exception as exc:  # noqa: BLE001 — surfaced to the GUI via status
            log.exception("%s failed", tag)
            db.rollback()
            row = fetch(db)
            if row is not None:
                row.status = "error"
                row.error_msg = str(exc)[:ERROR_MSG_MAX]
                db.commit()
    finally:
        if db_or_none is None:
            db.close()


def recover_stuck(db: Session, model_cls: type, *, in_flight: str, label: str) -> int:
    """Startup: flip rows a previous process left in flight to a visible
    error (background jobs die with the process). Returns the count; the
    caller commits once it has run every recovery."""
    stuck = db.query(model_cls).filter(model_cls.status == in_flight).all()
    for row in stuck:
        row.status = "error"
        row.error_msg = STUCK_MSG
    if stuck:
        log.warning("recovered %d stuck %s", len(stuck), label)
    return len(stuck)
