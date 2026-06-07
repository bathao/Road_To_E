"""Seed the singleton profile + lightweight column migrations. Idempotent."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.video_analysis.models import VAProfile

# Columns added to va_clip after the table first shipped. create_all() never
# alters existing tables, so add any missing ones by hand (SQLite ADD COLUMN).
_VA_CLIP_COLUMNS = {
    "me_side": "VARCHAR DEFAULT ''",
    "me_appearance": "VARCHAR DEFAULT ''",
    "subject_desc": "TEXT",
    "identified": "BOOLEAN DEFAULT 1",
    "preview_path": "VARCHAR",
}


def migrate(db: Session) -> None:
    cols = {row[1] for row in db.execute(text("PRAGMA table_info(va_clip)"))}
    changed = False
    for name, decl in _VA_CLIP_COLUMNS.items():
        if name not in cols:
            db.execute(text(f"ALTER TABLE va_clip ADD COLUMN {name} {decl}"))
            changed = True
    if changed:
        db.commit()


def seed_profile(db: Session) -> None:
    migrate(db)
    if db.get(VAProfile, 1) is None:
        db.add(VAProfile(id=1, name="Nguyễn Bá Thảo"))
        db.commit()
