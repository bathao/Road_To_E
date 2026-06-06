"""HTTP API for the Daily Tracker tab (prefix /api/tracker)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
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


# ---------------------------------------------------------------- categories
@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.sort_order).all()


# ---------------------------------------------------------------- last date
@router.get("/last-date")
def last_date(db: Session = Depends(get_db)):
    """The most recent date that has any data (for opening the grid there)."""
    candidates = [
        db.query(func.max(Activity.date)).scalar(),
        db.query(func.max(Match.date)).scalar(),
        db.query(func.max(PhysicalCheck.date)).scalar(),
    ]
    dates = [d for d in candidates if d is not None]
    latest = max(dates) if dates else None
    return {"date": latest.isoformat() if latest else None}


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
    existing = (
        db.query(Activity)
        .filter(Activity.date == payload.date, Activity.category_id == payload.category_id)
        .first()
    )
    if payload.duration_minutes <= 0 and not payload.note and not payload.is_package_start:
        if existing:
            db.delete(existing)
            db.commit()
        return None
    if existing:
        existing.duration_minutes = payload.duration_minutes
        existing.note = payload.note
        existing.is_package_start = payload.is_package_start
    else:
        existing = Activity(
            date=payload.date,
            category_id=payload.category_id,
            duration_minutes=payload.duration_minutes,
            note=payload.note,
            is_package_start=payload.is_package_start,
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
    # Place the new match after existing ones in the same cell.
    next_order = (
        db.query(Match)
        .filter(Match.date == payload.date, Match.category_id == payload.category_id)
        .count()
    )
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
        order_index=payload.order_index or next_order,
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


# ---------------------------------------------------------------- physical checklist
@router.get("/physical-items", response_model=list[schemas.PhysicalItemOut])
def list_physical_items():
    return [
        schemas.PhysicalItemOut(key=key, label=label)
        for key, label in service.PHYSICAL_ITEMS
    ]


@router.put("/physical-checks")
def set_physical_checks(payload: schemas.PhysicalChecksIn, db: Session = Depends(get_db)):
    """Replace the full set of ticked items for a day."""
    valid = {key for key, _ in service.PHYSICAL_ITEMS}
    wanted = [k for k in payload.items if k in valid]

    db.query(PhysicalCheck).filter(PhysicalCheck.date == payload.date).delete()
    for key in wanted:
        db.add(PhysicalCheck(date=payload.date, item_key=key))
    db.commit()
    return {"date": payload.date.isoformat(), "items": wanted}


# ---------------------------------------------------------------- day notes
@router.put("/day-notes")
def upsert_day_note(payload: schemas.DayNoteIn, db: Session = Depends(get_db)):
    """Upsert a day's note. Empty text deletes it."""
    text = (payload.text or "").strip()
    existing = db.query(DayNote).filter(DayNote.date == payload.date).first()
    if not text:
        if existing:
            db.delete(existing)
            db.commit()
        return {"date": payload.date.isoformat(), "text": ""}
    if existing:
        existing.text = text
    else:
        db.add(DayNote(date=payload.date, text=text))
    db.commit()
    return {"date": payload.date.isoformat(), "text": text}


# ---------------------------------------------------------------- events
@router.get("/events", response_model=list[schemas.EventOut])
def list_events(q: str = Query("", description="search term"), db: Session = Depends(get_db)):
    query = db.query(Event)
    if q:
        query = query.filter(Event.name.ilike(f"%{q}%"))
    return query.order_by(Event.name).limit(20).all()


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
