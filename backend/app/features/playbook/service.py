"""Business logic for the Tactical Playbook tab.

Tag-like fields are stored comma-separated on the row and exposed as lists. The
Library is static (see library.py) and only ever read here.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.features.playbook import library, schemas
from app.features.playbook.models import Tactic


# ---------------------------------------------------------------- tag helpers
def _join(items: list[str]) -> str | None:
    """List -> stored comma string (None when empty)."""
    cleaned = [s.strip() for s in items if s and s.strip()]
    return ", ".join(cleaned) or None


def _split(text: str | None) -> list[str]:
    """Stored comma string -> list."""
    if not text:
        return []
    return [s.strip() for s in text.split(",") if s.strip()]


def to_out(t: Tactic) -> schemas.TacticOut:
    return schemas.TacticOut(
        id=t.id,
        phase=t.phase,
        title=t.title,
        when_to_use=t.when_to_use,
        how_to=t.how_to,
        follow_up=t.follow_up,
        risk=t.risk,
        opponent_styles=_split(t.opponent_styles),
        tags=_split(t.tags),
        confidence=t.confidence,
        is_favorite=t.is_favorite,
        source_key=t.source_key,
        sort_order=t.sort_order,
    )


# ---------------------------------------------------------------- my tactics
def list_tactics(db: Session) -> list[schemas.TacticOut]:
    rows = (
        db.query(Tactic)
        .order_by(
            Tactic.is_favorite.desc(),
            Tactic.sort_order,
            Tactic.id,
        )
        .all()
    )
    return [to_out(t) for t in rows]


def _next_sort_order(db: Session, phase: str) -> int:
    last = (
        db.query(Tactic)
        .filter(Tactic.phase == phase)
        .order_by(Tactic.sort_order.desc())
        .first()
    )
    return (last.sort_order + 1) if last else 0


def create_tactic(db: Session, payload: schemas.TacticIn) -> schemas.TacticOut:
    t = Tactic(
        phase=payload.phase,
        title=payload.title,
        when_to_use=payload.when_to_use,
        how_to=payload.how_to,
        follow_up=payload.follow_up,
        risk=payload.risk,
        opponent_styles=_join(payload.opponent_styles),
        tags=_join(payload.tags),
        confidence=payload.confidence,
        is_favorite=payload.is_favorite,
        source_key=payload.source_key,
        sort_order=_next_sort_order(db, payload.phase),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return to_out(t)


def update_tactic(
    db: Session, tactic_id: int, payload: schemas.TacticIn
) -> schemas.TacticOut | None:
    t = db.get(Tactic, tactic_id)
    if t is None:
        return None
    t.phase = payload.phase
    t.title = payload.title
    t.when_to_use = payload.when_to_use
    t.how_to = payload.how_to
    t.follow_up = payload.follow_up
    t.risk = payload.risk
    t.opponent_styles = _join(payload.opponent_styles)
    t.tags = _join(payload.tags)
    t.confidence = payload.confidence
    t.is_favorite = payload.is_favorite
    t.source_key = payload.source_key
    db.commit()
    db.refresh(t)
    return to_out(t)


def delete_tactic(db: Session, tactic_id: int) -> bool:
    t = db.get(Tactic, tactic_id)
    if t is None:
        return False
    db.delete(t)
    db.commit()
    return True


def reorder(db: Session, ids: list[int]) -> None:
    """Apply a new display order; ids not present are left untouched."""
    for order, tactic_id in enumerate(ids):
        t = db.get(Tactic, tactic_id)
        if t is not None:
            t.sort_order = order
    db.commit()


# ---------------------------------------------------------------- library / meta
def get_library() -> list[schemas.LibraryItem]:
    return [schemas.LibraryItem(**item) for item in library.LIBRARY_TACTICS]


def get_meta() -> schemas.PlaybookMeta:
    return schemas.PlaybookMeta(
        phases=[schemas.PhaseMeta(key=k, label=label) for k, label in library.PHASES],
        spin_tags=library.SPIN_TAGS,
        placement_tags=library.PLACEMENT_TAGS,
        opponent_styles=library.OPPONENT_STYLES,
    )
