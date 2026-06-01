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
    DayRating,
    Event,
    Match,
    PhysicalCheck,
)

router = APIRouter(prefix="/api/tracker", tags=["tracker"])


# ---------------------------------------------------------------- categories
@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.sort_order).all()


# ---------------------------------------------------------------- week
@router.get("/weeks", response_model=schemas.WeekResponse)
def get_week(
    start: dt.date = Query(..., description="Monday of the week (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    return service.build_week(db, start)


# ---------------------------------------------------------------- activities
@router.put("/activities", response_model=schemas.ActivityOut | None)
def upsert_activity(payload: schemas.ActivityIn, db: Session = Depends(get_db)):
    """One call for the duration chips: upsert by (date, category). Empty -> delete."""
    existing = (
        db.query(Activity)
        .filter(Activity.date == payload.date, Activity.category_id == payload.category_id)
        .first()
    )
    if payload.duration_minutes <= 0 and not payload.note:
        if existing:
            db.delete(existing)
            db.commit()
        return None
    if existing:
        existing.duration_minutes = payload.duration_minutes
        existing.note = payload.note
    else:
        existing = Activity(
            date=payload.date,
            category_id=payload.category_id,
            duration_minutes=payload.duration_minutes,
            note=payload.note,
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


# ---------------------------------------------------------------- ratings
@router.put("/ratings", response_model=schemas.RatingOut | None)
def upsert_rating(payload: schemas.RatingIn, db: Session = Depends(get_db)):
    existing = db.query(DayRating).filter(DayRating.date == payload.date).first()
    if not payload.rating:
        if existing:
            db.delete(existing)
            db.commit()
        return None
    if existing:
        existing.rating = payload.rating
        existing.note = payload.note
    else:
        existing = DayRating(date=payload.date, rating=payload.rating, note=payload.note)
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


@router.delete("/ratings", status_code=204)
def delete_rating(date: dt.date = Query(...), db: Session = Depends(get_db)):
    obj = db.query(DayRating).filter(DayRating.date == date).first()
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
