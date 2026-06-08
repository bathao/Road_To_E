"""Seed the singleton profile + skill ledger + lightweight column migrations.
Idempotent."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.video_analysis.models import VAProfile, VASkill
from app.features.video_analysis.schemas import SKILL_ASPECTS

# Columns added to existing tables after they first shipped. create_all() never
# alters existing tables, so add any missing ones by hand (SQLite ADD COLUMN).
_VA_CLIP_COLUMNS = {
    "me_side": "VARCHAR DEFAULT ''",
    "me_appearance": "VARCHAR DEFAULT ''",
    "subject_desc": "TEXT",
    "identified": "BOOLEAN DEFAULT 1",
    "preview_path": "VARCHAR",
    "reviewed_at": "DATETIME",
    "processing_started_at": "DATETIME",
}

_VA_TRAIT_COLUMNS = {
    # Existing rows predate the review gate → treat them as 'proposed' (not yet
    # confirmed), per the user's choice to keep old data but not auto-accept it.
    "status": "VARCHAR DEFAULT 'proposed'",
    "ai_text": "TEXT",
    "reviewed_at": "DATETIME",
}


def _add_missing_columns(db: Session, table: str, columns: dict[str, str]) -> bool:
    existing = {row[1] for row in db.execute(text(f"PRAGMA table_info({table})"))}
    changed = False
    for name, decl in columns.items():
        if name not in existing:
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))
            changed = True
    return changed


def migrate(db: Session) -> None:
    changed = _add_missing_columns(db, "va_clip", _VA_CLIP_COLUMNS)
    changed = _add_missing_columns(db, "va_trait", _VA_TRAIT_COLUMNS) or changed
    if changed:
        db.commit()


def seed_profile(db: Session) -> None:
    migrate(db)
    if db.get(VAProfile, 1) is None:
        db.add(VAProfile(id=1, name="Nguyễn Bá Thảo"))
        db.commit()

    # One skill-ledger row per aspect (rating NULL until assessed).
    existing = {s.aspect for s in db.query(VASkill).all()}
    missing = [a for a in SKILL_ASPECTS if a not in existing]
    if missing:
        db.add_all(VASkill(aspect=a, status="neutral") for a in missing)
        db.commit()
