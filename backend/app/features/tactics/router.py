"""HTTP API for the Tactics tab (prefix /api/tactics)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.tactics import schemas, service

router = APIRouter(prefix="/api/tactics", tags=["tactics"])


@router.get("/opponents", response_model=list[schemas.OpponentOut])
def list_opponents(db: Session = Depends(get_db)):
    """Everyone the user has played against in SINGLES, most matches first —
    the picker. (H2H detail reuses GET /api/tracker/players/{id}/matches.)"""
    return service.list_opponents(db)


# ---------------------------------------------------------------- scouting facts
@router.get("/facts/{player_id}", response_model=schemas.FactsOut)
def get_facts(player_id: int, db: Session = Depends(get_db)):
    """Both scouting lists for one matchup: facts about ME (global) + about
    this opponent."""
    return service.list_facts(db, player_id)


@router.post("/facts", response_model=schemas.FactOut)
def add_fact(payload: schemas.FactIn, db: Session = Depends(get_db)):
    return service.add_fact(db, payload)


@router.put("/facts/{fact_id}", response_model=schemas.FactOut)
def update_fact(fact_id: int, payload: schemas.FactUpdate, db: Session = Depends(get_db)):
    try:
        return service.update_fact(db, fact_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Fact not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/facts/{fact_id}", response_model=schemas.OkOut)
def delete_fact(fact_id: int, db: Session = Depends(get_db)):
    service.delete_fact(db, fact_id)
    return schemas.OkOut()


# ------------------------------------------------------------------ reflections
@router.get("/reflections/{player_id}", response_model=list[schemas.ReflectionOut])
def list_reflections(player_id: int, db: Session = Depends(get_db)):
    """The student's own post-match analysis notes on this opponent, newest
    first. Subjective by design — the prompts cross-check them."""
    return service.list_reflections(db, player_id)


@router.post("/reflections", response_model=schemas.ReflectionOut)
def add_reflection(payload: schemas.ReflectionIn, db: Session = Depends(get_db)):
    try:
        return service.add_reflection(db, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Player not found")


@router.put("/reflections/{reflection_id}", response_model=schemas.ReflectionOut)
def update_reflection(
    reflection_id: int, payload: schemas.ReflectionUpdate, db: Session = Depends(get_db)
):
    try:
        return service.update_reflection(db, reflection_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Reflection not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/reflections/{reflection_id}", response_model=schemas.OkOut)
def delete_reflection(reflection_id: int, db: Session = Depends(get_db)):
    service.delete_reflection(db, reflection_id)
    return schemas.OkOut()


# ------------------------------------------------------------------- interview
@router.post("/interview", response_model=schemas.InterviewOut)
def interview(payload: schemas.InterviewIn, db: Session = Depends(get_db)):
    """The coach reads everything known about this matchup and asks ONLY for
    what's missing (max 5 questions). Synchronous — the local LLM call takes
    a moment; the button shows a spinner."""
    try:
        return service.run_interview(db, payload.player_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Player not found")


@router.post("/interview/answers", response_model=schemas.FactsOut)
def save_answers(payload: schemas.AnswersIn, db: Session = Depends(get_db)):
    """Answered questions become scouting facts ('me' answers are global —
    never re-asked). Blank answers are skipped. Returns the refreshed lists."""
    return service.save_answers(db, payload)


# ------------------------------------------------------------------- game plan
@router.get("/plan/{player_id}", response_model=schemas.PlanOut)
def get_plan(player_id: int, db: Session = Depends(get_db)):
    """The newest plan for this opponent (poll while status=`generating`);
    status=`empty` when none was ever generated."""
    return service.get_plan(db, player_id)


@router.post("/plan/{player_id}", response_model=schemas.PlanOut)
def generate_plan(
    player_id: int, background: BackgroundTasks, db: Session = Depends(get_db)
):
    """Start generating a game plan on a background task (slow: local LLM).
    Returns status=`generating`; poll GET /plan/{player_id}. 409 while one
    is already running for this opponent."""
    try:
        out = service.start_plan(db, player_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Player not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    background.add_task(service.run_plan_job, out.id)
    return out
