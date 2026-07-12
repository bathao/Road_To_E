"""HTTP API for the Head Coach tab (prefix /api/head-coach)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
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


@router.get("/sources", response_model=schemas.SourcesOut)
def get_sources(db: Session = Depends(get_db)):
    """The live source bundle without calling the AI (transparency view)."""
    return service.live_sources(db)
