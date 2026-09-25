"""Push the database snapshot to the shared read-only copy (2026-09-25).

Used by both the GUI button (POST /api/sync, local machine only) and
``backend/scripts/sync_prepare.py`` / ``sync.bat``. Steps:

1. ``prepare()`` — PRAGMA wal_checkpoint(TRUNCATE) so the committed main
   file is never stale (git ignores the -wal sidecar), then stamp
   ``backend/data/last_sync.txt`` (shown in the shared view's banner).
2. ``run_sync()`` — ``git add`` the DB + stamp; nothing staged for the DB →
   "nothing" (the stamp is reverted so no empty commit is made); otherwise
   ``git commit`` ONLY those two paths (code in progress stays untouched)
   and ``git push origin master`` → Render rebuilds the shared copy.

Git runs as a subprocess in the project root with the user's own
credentials (same as a push from the terminal).
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from app.core import settings

log = logging.getLogger(__name__)

DB_REL = "backend/data/tabletennis.db"
STAMP_REL = "backend/data/last_sync.txt"
COUNT_TABLES = ("tracker_match", "tracker_player", "tracker_session_note", "tracker_memo")


class SyncError(Exception):
    """A step failed; ``str(exc)`` is safe to show in the GUI."""


@dataclass
class GitResult:
    code: int
    out: str


GitRunner = Callable[[list[str], int], GitResult]


def _git(args: list[str], timeout: int = 30) -> GitResult:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=settings.PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:  # git not on PATH
        raise SyncError("git was not found on PATH (start the app from a shell that has git).") from exc
    except subprocess.TimeoutExpired as exc:
        raise SyncError(f"git {args[0]} timed out after {timeout}s.") from exc
    return GitResult(proc.returncode, (proc.stdout + proc.stderr).strip())


def prepare() -> tuple[str, dict[str, int]]:
    """Checkpoint the WAL and write the stamp. Returns (stamp, row counts).
    Raises SyncError when a writer blocks the checkpoint (nothing is stamped
    then, so a stale file is never committed)."""
    db_path = settings.DATABASE_PATH
    if not db_path.exists():
        raise SyncError(f"database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        busy, wal_pages, moved = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if busy:
            raise SyncError(
                "Checkpoint blocked: something is writing to the database. "
                "Finish the edit and try again."
            )
        counts = {
            t.removeprefix("tracker_"): conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in COUNT_TABLES
        }
    finally:
        conn.close()
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    settings.LAST_SYNC_PATH.write_text(stamp + "\n", encoding="utf-8")
    log.info("sync prepare: checkpoint ok (%s WAL pages, %s moved), stamped %s", wal_pages, moved, stamp)
    return stamp, counts


def run_sync(git: GitRunner = _git, prepare_fn: Callable[[], tuple[str, dict[str, int]]] = prepare) -> dict:
    """Full sync. Returns
    ``{"status": "pushed", "commit": <short sha>, "stamp": ..., "counts": {...}}`` or
    ``{"status": "nothing", "stamp": <previous stamp or None>, "counts": {...}}``.
    Raises SyncError with a GUI-ready message otherwise."""
    if settings.SHARE_MODE:
        raise SyncError("Sync only runs on the player's own machine.")

    stamp, counts = prepare_fn()

    res = git(["add", "--", DB_REL, STAMP_REL], 30)
    if res.code != 0:
        raise SyncError(f"git add failed:\n{res.out}")

    # Exit 0 = no staged change to the DB → nothing to publish. Undo the
    # stamp so the working tree stays clean (no commit with only a new time).
    res = git(["diff", "--cached", "--quiet", "--", DB_REL], 30)
    if res.code == 0:
        git(["reset", "-q", "--", STAMP_REL], 30)
        git(["checkout", "--", STAMP_REL], 30)
        return {"status": "nothing", "stamp": _read_stamp(), "counts": counts}
    if res.code != 1:
        raise SyncError(f"git diff failed:\n{res.out}")

    msg = f"DB sync {dt.date.today().isoformat()}"
    res = git(["commit", "-q", "-m", msg, "--", DB_REL, STAMP_REL], 60)
    if res.code != 0:
        raise SyncError(f"git commit failed:\n{res.out}")

    res = git(["push", "origin", "master"], 120)
    if res.code != 0:
        # The commit exists locally; the next sync (or sync.bat) pushes it.
        raise SyncError(f"git push failed (the commit is saved locally, try again):\n{res.out}")

    sha = git(["rev-parse", "--short", "HEAD"], 30)
    return {
        "status": "pushed",
        "commit": sha.out if sha.code == 0 else None,
        "stamp": stamp,
        "counts": counts,
    }


def _read_stamp() -> str | None:
    try:
        return settings.LAST_SYNC_PATH.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None
