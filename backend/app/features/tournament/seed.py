"""Tournament feature seed: idempotent column migrations."""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import _table_columns, add_missing_columns

log = logging.getLogger(__name__)

# level_limit shipped after the table did (2026-07-25, same day);
# points_limit = points-capped tournaments (2026-08-17).
_TOURNAMENT_COLUMNS = {
    "level_limit": "VARCHAR",
    "points_limit": "INTEGER",
    # knockout | league (user 2026-09-25). Existing rows default to knockout.
    "format": "VARCHAR NOT NULL DEFAULT 'knockout'",
}
_ENTRY_COLUMNS = {
    # Knocked out mid-event (user button 2026-08-15). Existing entries
    # default to 0 = still in.
    "eliminated": "BOOLEAN DEFAULT 0",
}


def migrate(db: Session) -> None:
    # One-off backfill, only in the same startup that ADDS the format column:
    # the leagues already registered by name ("BBTV League 10 - Week 1",
    # "BBTV League - Group 2", user 2026-09-25) become format=league. Never
    # re-run afterwards, so a later knockout event that happens to carry
    # "League" in its name keeps whatever the user picked in the form.
    backfill_leagues = "format" not in (_table_columns(db, "tournament") or {"format"})
    changed = add_missing_columns(db, "tournament", _TOURNAMENT_COLUMNS)
    if backfill_leagues:
        n = db.execute(
            text("UPDATE tournament SET format = 'league' WHERE lower(name) LIKE '%league%'")
        ).rowcount
        log.info("migrate: %d tournament(s) named *League* set to format=league", n)
    changed = add_missing_columns(db, "tournament_entry", _ENTRY_COLUMNS) or changed
    if changed:
        db.commit()
