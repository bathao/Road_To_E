"""Timestamp helpers."""
from __future__ import annotations

import datetime as dt


def as_utc(created: dt.datetime | None) -> dt.datetime | None:
    """Re-attach UTC to a naive SQLite timestamp so the API serialises it
    with an offset and the browser renders local time (SQLite stores the
    ``utcnow`` defaults without tzinfo)."""
    if created is not None and created.tzinfo is None:
        return created.replace(tzinfo=dt.timezone.utc)
    return created
