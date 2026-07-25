"""HTTP API for the Daily Tracker tab (prefix /api/tracker)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.tracker import schemas, service
from app.features.tracker.models import (
    Activity,
    Category,
    DayNote,
    Event,
    Match,
    PhysicalCheck,
)

router = APIRouter(prefix="/api/tracker", tags=["tracker"])


def _next_order(db: Session, date: dt.date, category_id: int) -> int:
    """Next free order_index in a cell — max+1, not count(), so the index
    stays unique after deletes/moves leave holes."""
    current_max = (
        db.query(Match.order_index)
        .filter(Match.date == date, Match.category_id == category_id)
        .order_by(Match.order_index.desc())
        .limit(1)
        .scalar()
    )
    return 0 if current_max is None else current_max + 1


# ---------------------------------------------------------------- categories
@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.sort_order).all()


# ---------------------------------------------------------------- last date
@router.get("/last-date", response_model=schemas.LastDateResponse)
def last_date(db: Session = Depends(get_db)):
    """The most recent date that has any data (for opening the grid there)."""
    return schemas.LastDateResponse(date=service.latest_data_date(db))


# ---------------------------------------------------------------- week
@router.get("/weeks", response_model=schemas.WeekResponse)
def get_week(
    start: dt.date = Query(..., description="First day of the grid (YYYY-MM-DD)"),
    end: dt.date | None = Query(
        None, description="Last day of the grid; defaults to start+6 (a week)"
    ),
    db: Session = Depends(get_db),
):
    return service.build_week(db, start, end)


# --------------------------------------------------------- coach packages
@router.get("/coach-packages", response_model=schemas.CoachPackagesResponse)
def get_coach_packages(db: Session = Depends(get_db)):
    """Current + historical 10-session coaching packages (range-independent)."""
    return service.compute_coach_packages(db)


@router.post(
    "/coach-packages/start-next", response_model=schemas.CoachPackagesResponse
)
def start_next_coach_package(db: Session = Depends(get_db)):
    """Flag the over-run block's (size+1)-th session as the new package's start
    (the one-click button on the Coach Package card)."""
    try:
        return service.start_next_coach_package(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/coach-package-start-allowed",
    response_model=schemas.CoachStartAllowedResponse,
)
def coach_package_start_allowed(
    date: dt.date = Query(..., description="Day to test (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """Whether a given day may be marked as the start of a new coaching package."""
    return schemas.CoachStartAllowedResponse(
        allowed=service.coach_package_start_allowed(db, date)
    )


# ---------------------------------------------------------------- activities
@router.put("/activities", response_model=schemas.ActivityOut | None)
def upsert_activity(payload: schemas.ActivityIn, db: Session = Depends(get_db)):
    """One call for the duration chips: upsert by (date, category). Empty -> delete."""
    rows = (
        db.query(Activity)
        .filter(Activity.date == payload.date, Activity.category_id == payload.category_id)
        .order_by(Activity.id)
        .all()
    )
    # Legacy DBs (created before the unique index) can hold duplicate rows for
    # the pair; a single-row delete would let the extra resurrect the value —
    # always collapse to one row.
    for extra in rows[1:]:
        db.delete(extra)
    existing = rows[0] if rows else None
    # A package can only start on a real session: a ★ on a 0-minute row would
    # show in the grid while being invisible to the package math.
    star = payload.is_package_start and payload.duration_minutes > 0
    if payload.duration_minutes <= 0 and not payload.note and not star:
        if existing:
            db.delete(existing)
        db.commit()
        return None
    if existing:
        existing.duration_minutes = payload.duration_minutes
        existing.note = payload.note
        existing.is_package_start = star
    else:
        existing = Activity(
            date=payload.date,
            category_id=payload.category_id,
            duration_minutes=payload.duration_minutes,
            note=payload.note,
            is_package_start=star,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    obj = db.get(Activity, activity_id)
    if obj:
        db.delete(obj)
        db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- matches
@router.post("/matches", response_model=schemas.MatchOut)
def create_match(payload: schemas.MatchIn, db: Session = Depends(get_db)):
    event = service.get_or_create_event(db, payload.event_name)
    match = Match(
        date=payload.date,
        category_id=payload.category_id,
        discipline=payload.discipline,
        best_of=payload.best_of,
        my_sets=payload.my_sets,
        opp_sets=payload.opp_sets,
        event_id=event.id if event else None,
        is_nonplaying=payload.is_nonplaying,
        nonplaying_label=payload.nonplaying_label,
        note=payload.note,
        order_index=(
            payload.order_index
            if payload.order_index is not None
            else _next_order(db, payload.date, payload.category_id)
        ),
        opponent_id=payload.opponent_id,
        opponent2_id=payload.opponent2_id,
        partner_id=payload.partner_id,
        handicap=payload.handicap or 0,
        handicap_pattern=service.normalize_handicap_pattern(payload.handicap_pattern),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return service.match_to_out(match)


@router.put("/matches/{match_id}", response_model=schemas.MatchOut)
def update_match(match_id: int, payload: schemas.MatchIn, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    event = service.get_or_create_event(db, payload.event_name)
    if (payload.date, payload.category_id) != (match.date, match.category_id):
        # Moved to another cell → append after that cell's existing matches so
        # order_index stays unique within the cell.
        match.order_index = _next_order(db, payload.date, payload.category_id)
    match.date = payload.date
    match.category_id = payload.category_id
    match.discipline = payload.discipline
    match.best_of = payload.best_of
    match.my_sets = payload.my_sets
    match.opp_sets = payload.opp_sets
    match.event_id = event.id if event else None
    match.is_nonplaying = payload.is_nonplaying
    match.nonplaying_label = payload.nonplaying_label
    match.note = payload.note
    match.opponent_id = payload.opponent_id
    match.opponent2_id = payload.opponent2_id
    match.partner_id = payload.partner_id
    match.handicap = payload.handicap or 0
    match.handicap_pattern = service.normalize_handicap_pattern(payload.handicap_pattern)
    db.commit()
    db.refresh(match)
    return service.match_to_out(match)


@router.delete("/matches/{match_id}", status_code=204)
def delete_match(match_id: int, db: Session = Depends(get_db)):
    obj = db.get(Match, match_id)
    if obj:
        db.delete(obj)
        db.commit()
    return Response(status_code=204)


@router.get(
    "/players/{player_id}/last-handicap",
    response_model=schemas.LastHandicapResponse,
)
def last_handicap(player_id: int, db: Session = Depends(get_db)):
    """Most recent singles handicap vs this opponent — the editor pre-fills
    the ratio when the opponent is picked (user can still change it)."""
    m = service.last_handicap_vs(db, player_id)
    if m is None:
        return schemas.LastHandicapResponse()
    return schemas.LastHandicapResponse(
        found=True, handicap=m.handicap or 0, handicap_pattern=m.handicap_pattern
    )


# ---------------------------------------------------------------- physical checklist
@router.get("/physical-items", response_model=list[schemas.PhysicalItemOut])
def list_physical_items():
    return [
        schemas.PhysicalItemOut(key=key, label=label)
        for key, label in service.PHYSICAL_ITEMS
    ]


@router.put("/physical-checks", response_model=schemas.PhysicalChecksOut)
def set_physical_checks(payload: schemas.PhysicalChecksIn, db: Session = Depends(get_db)):
    """Replace the full set of ticked items for a day."""
    valid = {key for key, _ in service.PHYSICAL_ITEMS}
    wanted = [k for k in payload.items if k in valid]

    db.query(PhysicalCheck).filter(PhysicalCheck.date == payload.date).delete()
    for key in wanted:
        db.add(PhysicalCheck(date=payload.date, item_key=key))
    db.commit()
    return schemas.PhysicalChecksOut(date=payload.date, items=wanted)


# ---------------------------------------------------------------- day notes
@router.put("/day-notes", response_model=schemas.DayNoteOut)
def upsert_day_note(payload: schemas.DayNoteIn, db: Session = Depends(get_db)):
    """Upsert a day's note. Empty text deletes it."""
    text = (payload.text or "").strip()
    existing = db.query(DayNote).filter(DayNote.date == payload.date).first()
    if not text:
        if existing:
            db.delete(existing)
            db.commit()
        return schemas.DayNoteOut(date=payload.date, text="")
    if existing:
        existing.text = text
    else:
        db.add(DayNote(date=payload.date, text=text))
    db.commit()
    return schemas.DayNoteOut(date=payload.date, text=text)


# ---------------------------------------------------------------- events
@router.get("/events", response_model=list[schemas.EventOut])
def list_events(q: str = Query("", description="search term"), db: Session = Depends(get_db)):
    query = db.query(Event)
    if q:
        query = query.filter(Event.name.ilike(f"%{q}%"))
    return query.order_by(Event.name).limit(20).all()


# ---------------------------------------------------------------- players
@router.get("/players", response_model=list[schemas.PlayerOut])
def list_players(q: str = Query("", description="search term"), db: Session = Depends(get_db)):
    """Opponent / partner pool, for the match-entry dropdown."""
    return service.list_players(db, q)


@router.post("/players", response_model=schemas.PlayerOut)
def create_player(payload: schemas.PlayerIn, db: Session = Depends(get_db)):
    """Add a new player (get-or-create by name) with a relative level."""
    return service.create_or_get_player(db, payload)


@router.put("/players/{player_id}", response_model=schemas.PlayerOut)
def update_player(player_id: int, payload: schemas.PlayerIn, db: Session = Depends(get_db)):
    updated = service.update_player(db, player_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return updated


# ---------------------------------------------------------------- stats
@router.get("/stats", response_model=schemas.StatsResponse)
def stats(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    return service.build_stats(db, date_from, date_to)


@router.get("/breakdown", response_model=schemas.BreakdownResponse)
def breakdown(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    unit: str = Query("month", pattern="^(month|week|day)$"),
    db: Session = Depends(get_db),
):
    return service.build_breakdown(db, date_from, date_to, unit)


@router.get("/match-stats", response_model=schemas.MatchStatsResponse)
def match_stats(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    discipline: str = Query("all", pattern="^(all|singles|doubles)$"),
    category: str = Query("all", pattern="^(all|practice|official)$"),
    unit: str = Query("month", pattern="^(month|week|day)$"),
    db: Session = Depends(get_db),
):
    """Match analytics over named-opponent matches only (for the Match Stats tab)."""
    return service.build_match_stats(db, date_from, date_to, discipline, category, unit)


# ---------------------------------------------------------------- export
@router.get("/export")
def export(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
):
    stamp = f"{date_from.isoformat()}_{date_to.isoformat()}"
    if format == "csv":
        data = service.export_csv(db, date_from, date_to)
        media = "text/csv"
        filename = f"tracker_{stamp}.csv"
    else:
        data = service.export_xlsx(db, date_from, date_to)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"tracker_{stamp}.xlsx"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
