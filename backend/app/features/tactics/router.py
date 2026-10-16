"""HTTP API for the Tactics tab (prefix /api/tactics).

Services raise app.core.errors (NotFound → 404, BadRequest → 400,
Conflict → 409); nothing is re-mapped here."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.tactics import matchlog, schemas, service

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
    return service.update_fact(db, fact_id, payload)


@router.delete("/facts/{fact_id}", response_model=schemas.OkOut)
def delete_fact(fact_id: int, db: Session = Depends(get_db)):
    service.delete_fact(db, fact_id)
    return schemas.OkOut()


# ------------------------------------------------------------------- interview
@router.post("/interview", response_model=schemas.InterviewOut)
def interview(payload: schemas.InterviewIn, db: Session = Depends(get_db)):
    """The coach reads everything known about this matchup and asks ONLY for
    what's missing (max 5 questions). Synchronous — the local LLM call takes
    a moment; the button shows a spinner."""
    return service.run_interview(db, payload.player_id)


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
    out = service.start_plan(db, player_id)
    background.add_task(service.run_plan_job, out.id)
    return out


@router.delete("/plan/{player_id}", response_model=schemas.OkOut)
def clear_plans(player_id: int, db: Session = Depends(get_db)):
    """Forget every generated plan for this opponent (status goes back to
    `empty`); scouting data is untouched."""
    service.clear_plans(db, player_id)
    return schemas.OkOut()


# -------------------------------------------------------------- match log
# Point-by-point charting of hand-picked singles matches (2026-10-10). The
# shot statistics the coach reads are derived server-side from the points.
@router.get("/serves", response_model=list[schemas.ServeOut])
def list_serves(db: Session = Depends(get_db)):
    """The user's serve repertoire — one-tap chips for every opponent."""
    return matchlog.list_serves(db)


@router.post("/serves", response_model=schemas.ServeOut)
def add_serve(payload: schemas.ServeIn, db: Session = Depends(get_db)):
    return matchlog.add_serve(db, payload)


@router.put("/serves/{serve_id}", response_model=schemas.ServeOut)
def update_serve(serve_id: int, payload: schemas.ServeIn, db: Session = Depends(get_db)):
    return matchlog.update_serve(db, serve_id, payload)


@router.delete("/serves/{serve_id}", response_model=schemas.OkOut)
def delete_serve(serve_id: int, db: Session = Depends(get_db)):
    matchlog.delete_serve(db, serve_id)
    return schemas.OkOut()


@router.get("/matchlog/status/{player_id}", response_model=list[schemas.MatchLogStatus])
def matchlog_status(player_id: int, db: Session = Depends(get_db)):
    """Which matches vs this opponent have points / set scores logged."""
    return matchlog.status_for_player(db, player_id)


@router.get("/matchlog/{match_id}", response_model=schemas.MatchLogOut)
def get_matchlog(match_id: int, db: Session = Depends(get_db)):
    """Typed set scores + every charted point of one singles match, plus the
    opponent's serves seen so far (across all charted matches vs them)."""
    return matchlog.get_matchlog(db, match_id)


@router.put("/matchlog/{match_id}/sets", response_model=list[schemas.SetOut])
def put_sets(match_id: int, payload: schemas.SetsIn, db: Session = Depends(get_db)):
    return matchlog.put_sets(db, match_id, payload)


@router.post("/matchlog/{match_id}/points", response_model=schemas.PointOut)
def add_point(match_id: int, payload: schemas.PointIn, db: Session = Depends(get_db)):
    """Append one rally to a set (point_no = next in that set)."""
    return matchlog.add_point(db, match_id, payload)


@router.put("/matchlog/points/{point_id}/note", response_model=schemas.PointOut)
def update_point_note(point_id: int, payload: schemas.PointNoteIn, db: Session = Depends(get_db)):
    return matchlog.update_point_note(db, point_id, payload)


@router.delete("/matchlog/points/{point_id}", response_model=schemas.OkOut)
def delete_point(point_id: int, db: Session = Depends(get_db)):
    """Delete one rally; later points of that set close the gap."""
    matchlog.delete_point(db, point_id)
    return schemas.OkOut()


@router.get("/matchlog/{match_id}/stats", response_model=schemas.StatsOut)
def match_stats(match_id: int, db: Session = Depends(get_db)):
    return matchlog.match_stats(db, match_id)


@router.get("/stats/{player_id}", response_model=schemas.StatsOut)
def player_stats(player_id: int, db: Session = Depends(get_db)):
    """Every charted match vs this opponent folded together — the numbers
    the coach's plan prompt will read."""
    return matchlog.player_stats(db, player_id)
