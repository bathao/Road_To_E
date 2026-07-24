"""backup_database: once-per-day snapshot, pruning, never blocks startup.

Uses tempfile directly instead of pytest's tmp_path: the machine's shared
pytest-of-* temp cache has broken ACLs, which errors every tmp_path setup.
"""
from __future__ import annotations

import datetime as dt
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import pytest

from app.core.backup import backup_database


@pytest.fixture()
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="tt-backup-test-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _make_db(path: Path) -> None:
    # closing(): sqlite3's `with` commits but does NOT close, and an open
    # handle keeps the file locked on Windows.
    with closing(sqlite3.connect(path)) as c, c:
        c.execute("CREATE TABLE t (x)")
        c.execute("INSERT INTO t VALUES (42)")


def test_backup_creates_once_per_day_and_prunes(tmp_dir):
    src = tmp_dir / "db.db"
    _make_db(src)
    bdir = tmp_dir / "backups"
    day = dt.date(2026, 7, 24)

    dest = backup_database(src, bdir, keep=3, today=day)
    assert dest is not None and dest.exists()
    with closing(sqlite3.connect(dest)) as c:  # snapshot is a working database
        assert c.execute("SELECT x FROM t").fetchone() == (42,)

    # Same day again -> skipped.
    assert backup_database(src, bdir, keep=3, today=day) is None

    # Across days only the newest `keep` snapshots survive.
    for i in range(1, 6):
        backup_database(src, bdir, keep=3, today=day + dt.timedelta(days=i))
    names = sorted(p.name for p in bdir.glob("*.db"))
    assert names == [
        "db-2026-07-27.db",
        "db-2026-07-28.db",
        "db-2026-07-29.db",
    ]


def test_backup_without_db_is_noop(tmp_dir):
    assert backup_database(tmp_dir / "nope.db", tmp_dir / "b") is None
    assert not (tmp_dir / "b").exists()
