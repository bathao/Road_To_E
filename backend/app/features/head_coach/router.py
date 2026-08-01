"""HTTP API for the Head Coach tab (prefix /api/head-coach)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.head_coach import schemas, service

router = APIRouter(prefix="/api/head-coach", tags=["head_coach"])


@router.get("/assessment", response_model=schemas.AssessmentOut)
def get_assessment(db: Session = Depends(get_db)):
    """The latest completed verdict (or an `empty` placeholder if none yet)."""
    return service.get_latest(db)


@router.post("/generate", response_model=schemas.AssessmentOut)
def generate(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Start generating a fresh verdict on a background task (slow: local LLM).

    Returns immediately with status=`generating`; poll GET /status until it is
    `done` (then refetch /assessment) or `error` (error_msg explains, e.g.
    Ollama not running)."""
    out = service.start_generate(db)
    background.add_task(service.run_generate_job, out.id)
    return out


@router.get("/status", response_model=schemas.GenerateStatusOut)
def get_status(db: Session = Depends(get_db)):
    """State of the most recent generation attempt (for polling)."""
    return service.get_status(db)


@router.get("/directive-progress", response_model=schemas.DirectiveProgressOut)
def get_directive_progress(db: Session = Depends(get_db)):
    """This week's database actual vs each trackable directive's weekly target."""
    return service.directive_progress(db)


# ------------------------------------------------------- weekly/monthly recap
@router.get("/recaps", response_model=schemas.RecapsOut)
def get_recaps(period: str = "week", db: Session = Depends(get_db)):
    """The most recently generated recap of one window type — read-only.
    Generation happens ONLY via POST /recaps/generate (explicit button)."""
    if period not in ("week", "month"):
        raise HTTPException(status_code=400, detail="period must be 'week' or 'month'")
    return service.get_recaps(db, period)


@router.post("/recaps/generate", response_model=schemas.RecapOut)
def generate_recap(
    payload: schemas.RecapGenerateIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Generate a recap of the window ending today (week = last 7 days,
    month = last 30 days, results up to now). Returns status=`generating`;
    poll GET /recaps until it leaves `generating`."""
    try:
        out = service.start_recap(db, payload.period_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    background.add_task(service.run_recap_job, out.id)
    return out


# ------------------------------------------------------------------ coach chat
@router.get("/chat", response_model=schemas.ChatHistoryOut)
def get_chat(db: Session = Depends(get_db)):
    """The full conversation (the coach's verbatim memory). While `pending`
    is true, keep polling — a reply is being generated in the background."""
    return service.chat_history(db)


@router.post("/chat", response_model=schemas.ChatHistoryOut)
def send_chat(
    payload: schemas.ChatSendIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send a message to the coach. Returns immediately with the pending
    coach row appended; poll GET /chat until `pending` is false."""
    try:
        out = service.start_chat(db, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    background.add_task(service.run_chat_job)
    return out


# --------------------------------------------------------------- coach notebook
@router.get("/notes", response_model=schemas.NotesOut)
def get_notes(db: Session = Depends(get_db)):
    """The coach's notebook (auto-written from chat + player-added)."""
    return service.list_notes(db)


@router.post("/notes", response_model=schemas.NotesOut)
def post_note(payload: schemas.NoteIn, db: Session = Depends(get_db)):
    """Add a notebook entry by hand."""
    return service.add_note(db, payload.text)


@router.delete("/notes/{note_id}", response_model=schemas.NotesOut)
def remove_note(note_id: int, db: Session = Depends(get_db)):
    """Remove one notebook entry (explicit player action)."""
    return service.delete_note(db, note_id)


@router.get("/debug", response_model=schemas.DebugOut)
def get_debug():
    """Dev panel: recent backend log lines + Ollama VRAM occupancy."""
    return service.debug_info()
