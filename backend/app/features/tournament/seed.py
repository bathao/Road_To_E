"""Tournament feature seed: idempotent column migrations."""
from sqlalchemy.orm import Session

from app.core.sqlite_migrate import add_missing_columns

# level_limit shipped after the table did (2026-07-25, same day).
_TOURNAMENT_COLUMNS = {
    "level_limit": "VARCHAR",
}


def migrate(db: Session) -> None:
    if add_missing_columns(db, "tournament", _TOURNAMENT_COLUMNS):
        db.commit()
