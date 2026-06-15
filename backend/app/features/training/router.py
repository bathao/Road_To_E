"""HTTP API for the Training Center tab (prefix /api/training)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.training import schemas, service

router = APIRouter(prefix="/api/training", tags=["training"])


@router.get("/today", response_model=schemas.SessionOut)
def get_today(db: Session = Depends(get_db)):
    """The currently-open session (created lazily; advances levels as needed)."""
    return service.get_today(db)


@router.get("/program", response_model=schemas.ProgramOut)
def get_program(level: str | None = None, db: Session = Depends(get_db)):
    """The full "Day" grid for a level (defaults to the current level)."""
    return service.program_grid(db, level)


@router.get("/levels", response_model=schemas.LevelOut)
def get_levels(db: Session = Depends(get_db)):
    return service.level_overview(db)


@router.get("/report", response_model=schemas.ReportOut)
def get_report(db: Session = Depends(get_db)):
    """Tier-1 brain view for the Head Coach: training load / adherence / volume."""
    return service.report(db)


@router.get("/session/{level}/{day_index}", response_model=schemas.SessionOut)
def get_session(level: str, day_index: int, db: Session = Depends(get_db)):
    """One materialised session by (level, day_index) — for viewing past days."""
    session = service.get_session_row(db, level, day_index)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return service.to_session_out(session)


@router.get("/session-by-date", response_model=schemas.SessionOut)
def get_session_by_date(date: dt.date, db: Session = Depends(get_db)):
    """The session completed on `date` — for the Daily Tracker Physical-row view."""
    session = service.session_on_date(db, date)
    if session is None:
        raise HTTPException(status_code=404, detail="No session on that date")
    return service.to_session_out(session)


@router.post(
    "/session/{level}/{day_index}/item/{item_id}", response_model=schemas.SessionOut
)
def tick_item(
    level: str,
    day_index: int,
    item_id: int,
    payload: schemas.TickIn,
    db: Session = Depends(get_db),
):
    """Tick / untick one exercise in a session (self-report, trusted)."""
    session = service.get_session_row(db, level, day_index)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    out = service.tick_item(db, session.id, item_id, payload.done)
    if out is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return out


@router.post(
    "/session/{level}/{day_index}/item/{item_id}/substitute",
    response_model=schemas.SessionOut,
)
def substitute_item(
    level: str,
    day_index: int,
    item_id: int,
    payload: schemas.SubstituteIn,
    db: Session = Depends(get_db),
):
    """Swap an exercise for a knee-safe alternative (e.g. the original hurt)."""
    session = service.get_session_row(db, level, day_index)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    out = service.substitute_item(db, session.id, item_id, payload.exercise_key)
    if out is None:
        raise HTTPException(status_code=404, detail="Item or alternative not found")
    return out


@router.post(
    "/session/{level}/{day_index}/item/{item_id}/skip",
    response_model=schemas.SessionOut,
)
def skip_item(
    level: str,
    day_index: int,
    item_id: int,
    payload: schemas.SkipIn,
    db: Session = Depends(get_db),
):
    """Mark an exercise skipped (logged — e.g. it aggravated the knee)."""
    session = service.get_session_row(db, level, day_index)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    out = service.skip_item(db, session.id, item_id, payload.skipped)
    if out is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return out


@router.post(
    "/session/{level}/{day_index}/complete", response_model=schemas.SessionOut
)
def complete_session(
    level: str,
    day_index: int,
    payload: schemas.CompleteIn,
    db: Session = Depends(get_db),
):
    """Finalise a session (+pain/RPE feedback → autoregulation); unlocks next.
    Accepts an optional backdated `done_on` (trained earlier, logged later)."""
    return service.complete_session(
        db, level, day_index, payload.note, payload.pain, payload.rpe,
        done_on=payload.done_on,
    )
