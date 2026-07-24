"""Daily on-startup snapshot of the SQLite database.

The whole project's value lives in one file (backend/data/tabletennis.db);
a bad migration, disk hiccup or fat-fingered delete would otherwise be
unrecoverable. Every server start copies the DB to backups/ (at most once
per day) and prunes old snapshots. Uses the sqlite3 backup API, which is
WAL-safe — a plain file copy could miss commits still sitting in the -wal
sidecar.
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from pathlib import Path

from app.core.settings import DATA_DIR, DATABASE_PATH

log = logging.getLogger(__name__)

BACKUP_DIR = DATA_DIR / "backups"
KEEP_BACKUPS = 30  # ~a month of daily snapshots


def backup_database(
    src: Path = DATABASE_PATH,
    backup_dir: Path = BACKUP_DIR,
    keep: int = KEEP_BACKUPS,
    today: dt.date | None = None,
) -> Path | None:
    """Snapshot `src` into backup_dir (once per day), prune to `keep` newest.

    Returns the snapshot path, or None when skipped (no DB yet / already
    backed up today / backup failed — a backup failure must never prevent
    the app from starting)."""
    if not src.exists():
        return None  # first run — nothing to protect yet
    day = today or dt.date.today()
    dest = backup_dir / f"{src.stem}-{day.isoformat()}{src.suffix}"
    if dest.exists():
        return None  # today's snapshot already taken
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Close explicitly: sqlite3's `with` is a transaction context, NOT a
        # closer — a lingering handle keeps the file locked on Windows and
        # pruning (or the next backup) would fail with WinError 32.
        conn = sqlite3.connect(src)
        try:
            out = sqlite3.connect(dest)
            try:
                conn.backup(out)
            finally:
                out.close()
        finally:
            conn.close()
        # Prune: newest `keep` stay (ISO-dated names sort chronologically).
        snapshots = sorted(backup_dir.glob(f"{src.stem}-*{src.suffix}"))
        for old in snapshots[:-keep] if keep > 0 else []:
            old.unlink()
        log.info("database backed up to %s (%d snapshot(s) kept)",
                 dest.name, min(len(snapshots), keep))
        return dest
    except Exception:  # noqa: BLE001 — never block startup on a backup
        log.exception("database backup failed")
        if dest.exists():  # don't leave a half-written snapshot behind
            try:
                dest.unlink()
            except OSError:
                pass
        return None
