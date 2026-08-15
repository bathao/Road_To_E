"""Tournament feature seed: idempotent column migrations."""
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import add_missing_columns

# level_limit shipped after the table did (2026-07-25, same day).
_TOURNAMENT_COLUMNS = {
    "level_limit": "VARCHAR",
}
_ENTRY_COLUMNS = {
    # Knocked out mid-event (user button 2026-08-15). Existing entries
    # default to 0 = still in.
    "eliminated": "BOOLEAN DEFAULT 0",
}


def migrate(db: Session) -> None:
    changed = add_missing_columns(db, "tournament", _TOURNAMENT_COLUMNS)
    changed = add_missing_columns(db, "tournament_entry", _ENTRY_COLUMNS) or changed
    if changed:
        db.commit()
