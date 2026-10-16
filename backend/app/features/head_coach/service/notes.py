"""The coach's notebook (CoachNote rows).

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.features.head_coach import schemas
from app.features.head_coach.models import (
    CoachNote,
)

from .common import _tz


# --------------------------------------------------------------- coach notebook
def list_notes(db: Session) -> schemas.NotesOut:
    rows = db.query(CoachNote).order_by(CoachNote.created_at.desc(), CoachNote.id.desc()).all()
    return schemas.NotesOut(
        notes=[
            schemas.NoteOut(
                id=r.id, created_at=_tz(r.created_at), text=r.text, source=r.source
            )
            for r in rows
        ]
    )


def add_note(db: Session, text: str) -> schemas.NotesOut:
    db.add(CoachNote(text=text.strip(), source="user"))
    db.commit()
    return list_notes(db)


def delete_note(db: Session, note_id: int) -> schemas.NotesOut:
    """Player-initiated removal of one notebook entry (explicit UI action)."""
    row = db.get(CoachNote, note_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return list_notes(db)
