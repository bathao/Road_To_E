"""HTTP API for the Head Coach tab (prefix /api/head-coach)."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.head_coach import schemas, service

router = APIRouter(prefix="/api/head-coach", tags=["head_coach"])


@router.get("/assessment", response_model=schemas.AssessmentOut)
def get_assessment(db: Session = Depends(get_db)):
    """The latest generated verdict (or an `empty` placeholder if none yet)."""
    return service.get_latest(db)


@router.post("/generate", response_model=schemas.AssessmentOut)
def generate(db: Session = Depends(get_db)):
    """Gather the specialist reports and synthesise a fresh verdict (slow: local LLM)."""
    try:
        return service.generate(db)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Không gọi được model cục bộ ({service.HEAD_COACH_MODEL}). "
            f"Hãy chắc chắn Ollama đang chạy. Chi tiết: {e}",
        )


@router.get("/sources", response_model=schemas.SourcesOut)
def get_sources(db: Session = Depends(get_db)):
    """The live source bundle without calling the AI (transparency view)."""
    return service.live_sources(db)
