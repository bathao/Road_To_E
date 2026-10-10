"""HTTP API for the Tactics tab (prefix /api/tactics)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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
def add_reflection(
    payload: schemas.ReflectionIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Save the note, then (background, best-effort) let the coach extract
    anything it reveals about the STUDENT into the global me-file."""
    try:
        row = service.add_reflection(db, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Player not found")
    background.add_task(service.run_me_extraction_job, row.id)
    return row


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
    try:
        return matchlog.update_serve(db, serve_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Serve not found")


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
    try:
        return matchlog.get_matchlog(db, match_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Singles match not found")


@router.put("/matchlog/{match_id}/sets", response_model=list[schemas.SetOut])
def put_sets(match_id: int, payload: schemas.SetsIn, db: Session = Depends(get_db)):
    try:
        return matchlog.put_sets(db, match_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Singles match not found")


@router.post("/matchlog/{match_id}/points", response_model=schemas.PointOut)
def add_point(match_id: int, payload: schemas.PointIn, db: Session = Depends(get_db)):
    """Append one rally to a set (point_no = next in that set)."""
    try:
        return matchlog.add_point(db, match_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Singles match not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/matchlog/points/{point_id}/note", response_model=schemas.PointOut)
def update_point_note(point_id: int, payload: schemas.PointNoteIn, db: Session = Depends(get_db)):
    try:
        return matchlog.update_point_note(db, point_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Point not found")


@router.delete("/matchlog/points/{point_id}", response_model=schemas.OkOut)
def delete_point(point_id: int, db: Session = Depends(get_db)):
    """Delete one rally; later points of that set close the gap."""
    matchlog.delete_point(db, point_id)
    return schemas.OkOut()


@router.get("/matchlog/{match_id}/stats", response_model=schemas.StatsOut)
def match_stats(match_id: int, db: Session = Depends(get_db)):
    try:
        return matchlog.match_stats(db, match_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Singles match not found")


@router.get("/stats/{player_id}", response_model=schemas.StatsOut)
def player_stats(player_id: int, db: Session = Depends(get_db)):
    """Every charted match vs this opponent folded together — the numbers
    the coach's plan prompt will read."""
    return matchlog.player_stats(db, player_id)
