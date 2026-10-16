"""Tactics feature seed: column migrations, startup recovery, and the user's
initial serve repertoire."""
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import add_missing_columns
from app.features.tactics.service import recover_stuck_plans
from app.features.tactics.models import TacticServe
from app.features.tracker.models import Setting

_FACT_COLUMNS = {
    # Canonical intake slot (2026-08-17 structured-intake rework). Existing
    # free-form facts stay key-less.
    "key": "VARCHAR",
}

# The user's six serves as dictated on 2026-10-10 ("Đứng lệch phải, giao
# bóng xoáy xuống ngắn phải" …). Names are the user's own words (Vietnamese
# by request); attributes are the fixed English codes. Seeded ONCE (marker
# row in tracker_setting) so later edits/deletions in the GUI stick.
_SERVES_SEED_KEY = "tactic_serves_seeded"
_INITIAL_SERVES = [
    ("Lệch phải · xoáy xuống ngắn phải", "right", "back", "short", "R"),
    ("Lệch phải · lỏng ngắn phải", "right", "none", "short", "R"),
    ("Lệch phải · sốc dài xoáy lên trái", "right", "top", "long", "L"),
    ("Lệch phải · ngang-xuống dài trái", "right", "sideback", "long", "L"),
    ("Giữa bàn · xoáy xuống ngắn phải", "center", "back", "short", "R"),
    ("Giữa bàn · xoáy xuống ngắn trái", "center", "back", "short", "L"),
]


def seed_serves(db: Session) -> bool:
    """Insert the initial repertoire once. Returns True when it did."""
    if db.get(Setting, _SERVES_SEED_KEY) is not None:
        return False
    if db.query(TacticServe).count() == 0:
        for i, (name, stance, spin, length, place) in enumerate(_INITIAL_SERVES):
            db.add(TacticServe(
                name=name, stance=stance, motion=None, spin=spin, amount=None,
                length=length, place=place, sort_order=i + 1,
            ))
    db.add(Setting(key=_SERVES_SEED_KEY, value="1"))
    db.commit()
    return True


def migrate(db: Session) -> None:
    if add_missing_columns(db, "tactic_fact", _FACT_COLUMNS):
        db.commit()
    seed_serves(db)
    recover_stuck_plans(db)
