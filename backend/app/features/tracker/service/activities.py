"""Duration chips (activities), the legacy physical checklist, day notes,
categories and events — the Daily Tracker's simple writes.

Moved out of router.py 2026-10-16 (REFACTOR.md §3.4): the router only maps
HTTP to these calls now.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.features.tracker import schemas
from app.features.tracker.models import (
    Activity,
    Category,
    Coach,
    DayNote,
    Event,
    PhysicalCheck,
)

from .coaches import default_coach_id
from .grid import PHYSICAL_ITEMS

# The event autocomplete shows at most this many names.
EVENT_SEARCH_LIMIT = 20


def list_categories(db: Session) -> list[Category]:
    return db.query(Category).order_by(Category.sort_order).all()


def list_events(db: Session, q: str = "") -> list[Event]:
    """Event names matching `q` (substring, case-insensitive), A→Z."""
    query = db.query(Event)
    if q:
        query = query.filter(Event.name.ilike(f"%{q}%"))
    return query.order_by(Event.name).limit(EVENT_SEARCH_LIMIT).all()


def upsert_activity(db: Session, payload: schemas.ActivityIn) -> Activity | None:
    """One call for the duration chips: upsert by (date, category). Empty →
    delete (returns None)."""
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

    # The coach stamp is a train_with_coach concern only. Payload names a
    # coach -> validate and use it; payload omits it -> keep the stored one
    # (legacy callers), defaulting to the is_default coach on brand-new rows.
    category = db.get(Category, payload.category_id)
    coach_id: int | None = None
    if category is not None and category.key == "train_with_coach":
        if payload.coach_id is not None:
            if db.get(Coach, payload.coach_id) is None:
                raise BadRequest("Unknown coach")
            coach_id = payload.coach_id
        else:
            coach_id = (
                existing.coach_id if existing else None
            ) or default_coach_id(db)

    # A package can only start on a real session: a ★ on a 0-minute row would
    # show in the grid while being invisible to the package math. A pay-per-
    # session coach's ★ is equally invisible — strip it instead of storing a
    # mark the package math ignores.
    star = payload.is_package_start and payload.duration_minutes > 0
    if star and coach_id is not None:
        coach = db.get(Coach, coach_id)
        if coach is not None and not coach.counts_package:
            star = False
    if payload.duration_minutes <= 0 and not payload.note and not star:
        if existing:
            db.delete(existing)
        db.commit()
        return None
    if existing:
        existing.duration_minutes = payload.duration_minutes
        existing.note = payload.note
        existing.is_package_start = star
        existing.coach_id = coach_id
    else:
        existing = Activity(
            date=payload.date,
            category_id=payload.category_id,
            duration_minutes=payload.duration_minutes,
            note=payload.note,
            is_package_start=star,
            coach_id=coach_id,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def set_physical_checks(
    db: Session, payload: schemas.PhysicalChecksIn
) -> schemas.PhysicalChecksOut:
    """Replace the full set of ticked legacy checklist items for a day
    (unknown keys are dropped)."""
    valid = {key for key, _ in PHYSICAL_ITEMS}
    wanted = [k for k in payload.items if k in valid]
    db.query(PhysicalCheck).filter(PhysicalCheck.date == payload.date).delete()
    for key in wanted:
        db.add(PhysicalCheck(date=payload.date, item_key=key))
    db.commit()
    return schemas.PhysicalChecksOut(date=payload.date, items=wanted)


def upsert_day_note(db: Session, payload: schemas.DayNoteIn) -> schemas.DayNoteOut:
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
