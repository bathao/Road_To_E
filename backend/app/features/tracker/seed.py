"""Seed / reconcile the default grid rows (categories) shown in the sheet.

The 'Overall' row is auto-generated (see service.compute_overall_colors), not
edited by hand, but it is still a category so it renders as a grid row.
"""
import logging

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import add_missing_columns
from app.features.tracker.models import Activity, Category, Match

log = logging.getLogger(__name__)

# Columns added to existing tables after they first shipped.
_PLAYER_COLUMNS = {
    # Opponent uses pimpled rubber ("đánh gai"). Existing players default to 0.
    "plays_pips": "BOOLEAN DEFAULT 0",
    # BBTV Open points (Database tab); NULL = not rated yet.
    "points": "INTEGER",
}
_MATCH_COLUMNS = {
    # Per-set handicap sequence ("2-0-2"); NULL = uniform handicap (existing
    # rows stay as-is — the signed `handicap` int already carries them).
    "handicap_pattern": "VARCHAR",
    # Player points frozen at match time (ELO); NULL = legacy row → replay
    # falls back to the player's current points.
    "opp_points_snap": "INTEGER",
    "opp2_points_snap": "INTEGER",
    "partner_points_snap": "INTEGER",
}


def migrate(db: Session) -> None:
    """Idempotent column migrations for tables that predate a new field."""
    changed = add_missing_columns(db, "tracker_player", _PLAYER_COLUMNS)
    changed = add_missing_columns(db, "tracker_match", _MATCH_COLUMNS) or changed
    changed = _ensure_activity_unique_index(db) or changed
    if changed:
        db.commit()


def _ensure_activity_unique_index(db: Session) -> bool:
    """Back the (date, category_id) upsert in the router with a real unique index.

    NEVER deletes or merges rows: if duplicates already exist the index cannot
    be created — log a warning and leave the data exactly as it is.
    """
    try:
        db.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_tracker_activity_date_category "
                "ON tracker_activity (date, category_id)"
            )
        )
        return True
    except OperationalError:
        db.rollback()
        log.warning(
            "tracker_activity has duplicate (date, category_id) rows; unique "
            "index not created. Data left untouched — resolve duplicates by hand."
        )
        return False


# (key, label, type, color_group). Order here = display order (sort_order).
DEFAULT_CATEGORIES = [
    ("train_with_coach", "Train with Coach", "duration", "green"),
    ("training_with_partner", "Training with Partner", "duration", "green"),
    ("serve", "Serve", "duration", "green"),
    ("physical_training", "Physical Training", "checklist", "yellow"),
    ("practice_match", "Practice Match", "match", "none"),
    ("official_match", "Official Match", "match", "none"),
    # Tournament play (đánh giải) — kept separate from official (đánh độ nhẹ)
    # so the ELO rating can weight it higher (t = 1.5, see service ELO_KIND_MULT).
    ("tournament_match", "Tournament Match", "match", "none"),
    # Auto-computed row (like Overall): coach + partner minutes + match sets
    # × service.RACKET_MINUTES_PER_SET. Read-only in the grid.
    ("racket_time", "Racket Time", "computed", "none"),
    ("notes", "Notes", "note", "none"),
    ("overall", "Overall", "rating", "none"),
]


def seed_categories(db: Session) -> None:
    """Reconcile the category table to DEFAULT_CATEGORIES. Idempotent.

    - Inserts any missing categories.
    - Keeps label/type/color/sort_order in sync with the defaults.
    - NEVER deletes: a category missing from the defaults (rename/typo in this
      file, downgrade, …) is kept along with all its activities/matches — user
      data must survive a code change. It is only logged so the mismatch is
      visible.
    """
    migrate(db)
    desired_keys = {key for key, *_ in DEFAULT_CATEGORIES}
    existing = {c.key: c for c in db.query(Category).all()}
    changed = False

    for key, cat in existing.items():
        if key not in desired_keys:
            n_act = db.query(Activity).filter(Activity.category_id == cat.id).count()
            n_match = db.query(Match).filter(Match.category_id == cat.id).count()
            log.warning(
                "category %r is not in DEFAULT_CATEGORIES; keeping it and its "
                "data (%d activities, %d matches). Remove by hand if intended.",
                key,
                n_act,
                n_match,
            )

    # Insert missing / update existing to match the defaults.
    for order, (key, label, type_, color) in enumerate(DEFAULT_CATEGORIES):
        cat = existing.get(key)
        if cat is None:
            db.add(
                Category(
                    key=key,
                    label=label,
                    type=type_,
                    color_group=color,
                    sort_order=order,
                )
            )
            changed = True
        elif (
            cat.label != label
            or cat.type != type_
            or cat.color_group != color
            or cat.sort_order != order
        ):
            cat.label = label
            cat.type = type_
            cat.color_group = color
            cat.sort_order = order
            changed = True

    if changed:
        db.commit()
