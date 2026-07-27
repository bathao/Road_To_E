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
    changed = _rebuild_match_player_fks(db) or changed
    if changed:
        db.commit()


def _rebuild_match_player_fks(db: Session) -> bool:
    """One-time rebuild of tracker_match so the PLAYER columns get real FK
    constraints.

    opponent_id/opponent2_id/partner_id were ALTER-added, and SQLite cannot
    attach a FK constraint in ALTER TABLE — so on DBs that predate those
    columns, PRAGMA foreign_keys has nothing to enforce there. Rebuild per
    sqlite.org/lang_altertable.html: create from the canonical model DDL,
    copy every row by name, verify the count, drop the old table, rename.
    Idempotent (skips when the player FKs already exist) and NEVER destroys
    data: any dangling id or copy mismatch aborts with the original intact.
    """
    refs = {
        row[2] for row in db.execute(text("PRAGMA foreign_key_list(tracker_match)"))
    }
    if "tracker_player" in refs:
        return False

    # A dangling player id would make the copy fail mid-way — check first and
    # leave everything untouched (the user decides how to fix such rows).
    dangling = db.execute(text(
        "SELECT COUNT(*) FROM tracker_match m WHERE "
        "(m.opponent_id IS NOT NULL AND NOT EXISTS "
        " (SELECT 1 FROM tracker_player p WHERE p.id = m.opponent_id)) OR "
        "(m.opponent2_id IS NOT NULL AND NOT EXISTS "
        " (SELECT 1 FROM tracker_player p WHERE p.id = m.opponent2_id)) OR "
        "(m.partner_id IS NOT NULL AND NOT EXISTS "
        " (SELECT 1 FROM tracker_player p WHERE p.id = m.partner_id))"
    )).scalar()
    if dangling:
        log.warning(
            "tracker_match FK rebuild skipped: %s rows reference missing "
            "players — fix them first", dangling,
        )
        return False

    from sqlalchemy.schema import CreateIndex, CreateTable

    bind = db.get_bind()
    ddl = str(CreateTable(Match.__table__).compile(bind)).replace(
        "CREATE TABLE tracker_match", "CREATE TABLE tracker_match_rebuild", 1
    )
    cols = ", ".join(c.name for c in Match.__table__.columns)
    try:
        db.execute(text(ddl))
        db.execute(text(
            f"INSERT INTO tracker_match_rebuild ({cols}) "
            f"SELECT {cols} FROM tracker_match"
        ))
        old_n = db.execute(text("SELECT COUNT(*) FROM tracker_match")).scalar()
        new_n = db.execute(
            text("SELECT COUNT(*) FROM tracker_match_rebuild")
        ).scalar()
        if old_n != new_n:
            db.rollback()
            log.error(
                "tracker_match FK rebuild aborted: %s vs %s rows", old_n, new_n
            )
            return False
        db.execute(text("DROP TABLE tracker_match"))
        db.execute(text("ALTER TABLE tracker_match_rebuild RENAME TO tracker_match"))
        for idx in Match.__table__.indexes:
            db.execute(text(str(CreateIndex(idx).compile(bind))))
    except OperationalError:
        db.rollback()
        log.exception("tracker_match FK rebuild failed — original table kept")
        return False
    log.info("tracker_match rebuilt with player FK constraints (%s rows)", new_n)
    return True


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
