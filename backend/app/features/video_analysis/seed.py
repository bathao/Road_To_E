"""Seed the singleton profile + per-setting skill ledger + migrate away from the
old video pipeline. Idempotent.

The Technique Analysis tab dropped local video processing. ``create_all`` makes
the new tables (``va_report``, ``va_skill_snapshot``); this migration drops the
dead video tables, adds ``source_report_id`` to ``va_trait`` + ``setting`` to
``va_report``/``va_skill_snapshot``, and rebuilds ``va_skill`` so it is keyed per
(aspect, setting) — a separate rating for practice vs match. Profile basics are
preserved.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.video_analysis.models import VAProfile, VASkill
from app.features.video_analysis.schemas import SETTINGS, SKILL_ASPECTS

# Tables from the abandoned local-VLM/CV pipeline — no longer mapped. The DB had
# no accepted findings, so nothing valuable is lost (their proposed traits, if
# any, are left orphaned via va_trait.source_clip_id, which is now a dead column).
_DROPPED_TABLES = ("va_clip", "va_analysis", "va_metric", "va_profile_image")

# Columns added to existing tables after they first shipped. create_all() never
# alters existing tables, so add any missing ones by hand (SQLite ADD COLUMN).
_VA_TRAIT_COLUMNS = {
    "source_report_id": "INTEGER",  # FK va_report (replaces the dead source_clip_id)
    "status": "VARCHAR DEFAULT 'proposed'",
    "ai_text": "TEXT",
    "reviewed_at": "DATETIME",
}

_VA_REPORT_COLUMNS = {
    # practice = tập luyện/khởi động; match = thi đấu trận thật. Old rows default
    # to practice (most early clips were training).
    "setting": "VARCHAR DEFAULT 'practice'",
}

_VA_SNAPSHOT_COLUMNS = {
    "setting": "VARCHAR DEFAULT 'practice'",
}


def _columns(db: Session, table: str) -> set[str]:
    return {row[1] for row in db.execute(text(f"PRAGMA table_info({table})"))}


def _add_missing_columns(db: Session, table: str, columns: dict[str, str]) -> bool:
    existing = _columns(db, table)
    if not existing:  # table doesn't exist yet — create_all will make it
        return False
    changed = False
    for name, decl in columns.items():
        if name not in existing:
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))
            changed = True
    return changed


def migrate(db: Session) -> None:
    changed = _add_missing_columns(db, "va_trait", _VA_TRAIT_COLUMNS)
    changed = _add_missing_columns(db, "va_report", _VA_REPORT_COLUMNS) or changed
    changed = _add_missing_columns(db, "va_skill_snapshot", _VA_SNAPSHOT_COLUMNS) or changed

    # va_skill: the rating is now tracked per (aspect, setting), so the table must
    # have a `setting` column + a composite unique on (aspect, setting). The old
    # table (unique on `aspect` alone) can't be altered in place → drop & recreate
    # once. ONE-TIME: only when the column is missing, so real ratings aren't wiped
    # on every boot. (The old rows were unrated scaffold; nothing lost.)
    skill_cols = _columns(db, "va_skill")
    if skill_cols and "setting" not in skill_cols:
        db.execute(text("DROP TABLE va_skill"))
        db.commit()
        VASkill.__table__.create(bind=db.get_bind(), checkfirst=True)
        changed = True

    for tbl in _DROPPED_TABLES:
        db.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
        changed = True
    if changed:
        db.commit()


def seed_profile(db: Session) -> None:
    migrate(db)
    if db.get(VAProfile, 1) is None:
        db.add(VAProfile(id=1, name="Nguyễn Bá Thảo"))
        db.commit()

    # One skill-ledger row per (aspect, setting) — practice + match (rating NULL
    # until assessed for that setting).
    existing = {(s.aspect, s.setting) for s in db.query(VASkill).all()}
    missing = [
        (a, st)
        for a in SKILL_ASPECTS
        for st in SETTINGS
        if (a, st) not in existing
    ]
    if missing:
        db.add_all(VASkill(aspect=a, setting=st, status="neutral") for a, st in missing)
        db.commit()
