"""Prepare the database for a sync commit (called by sync.bat).

1. PRAGMA wal_checkpoint(TRUNCATE): the app runs SQLite in WAL mode and git
   ignores the -wal sidecar, so a commit made while start.bat is running
   would otherwise snapshot a STALE main file (TODO.md watch-list item,
   bitten 2026-08-23). Works while the app is running (busy_timeout).
2. Stamp backend/data/last_sync.txt with the local time; the shared view's
   banner shows it as "Last synced ...".

Exit code 1 (and no stamp) when the checkpoint could not complete, so
sync.bat stops before committing a stale file.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_DIR / "data" / "tabletennis.db"
STAMP_PATH = BACKEND_DIR / "data" / "last_sync.txt"


def main() -> int:
    if not DB_PATH.exists():
        print(f"database not found: {DB_PATH}")
        return 1
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        busy, wal_pages, moved = conn.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        if busy:
            print(
                "checkpoint BLOCKED (a writer is holding the database). "
                "Finish what the app is doing, then run sync.bat again."
            )
            return 1
        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("tracker_match", "tracker_player", "tracker_session_note", "tracker_memo")
        }
    finally:
        conn.close()
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    STAMP_PATH.write_text(stamp + "\n", encoding="utf-8")
    print(f"checkpoint OK ({wal_pages} WAL pages, {moved} moved) - stamped {stamp}")
    print("  " + ", ".join(f"{k.removeprefix('tracker_')}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
