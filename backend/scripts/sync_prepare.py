"""Prepare the database for a sync commit (called by sync.bat).

Thin CLI over ``app.core.syncer.prepare``: WAL checkpoint + last_sync.txt
stamp. Exit code 1 (and no stamp) when the checkpoint could not complete,
so sync.bat stops before committing a stale file. The GUI's "Sync to coach"
button runs the same code plus the git steps (``syncer.run_sync``).
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.syncer import SyncError, prepare  # noqa: E402


def main() -> int:
    try:
        stamp, counts = prepare()
    except SyncError as exc:
        print(str(exc))
        return 1
    print(f"checkpoint OK - stamped {stamp}")
    print("  " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
