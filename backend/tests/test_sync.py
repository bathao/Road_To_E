"""GUI "Sync to coach" (2026-09-25): POST /api/sync = checkpoint + commit the
DB snapshot + push. Git and the checkpoint are faked — a test must never
touch the real repo or database."""
from __future__ import annotations

import pytest

from app.core import settings, syncer
from app.core.syncer import GitResult, SyncError


class FakeGit:
    """Records every git call; `diff --cached --quiet` answers `db_changed`,
    `push` answers `push_ok`."""

    def __init__(self, db_changed: bool, push_ok: bool = True):
        self.db_changed = db_changed
        self.push_ok = push_ok
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], timeout: int) -> GitResult:
        self.calls.append(args)
        if args[0] == "diff":
            return GitResult(1 if self.db_changed else 0, "")
        if args[0] == "push":
            return GitResult(0 if self.push_ok else 1, "" if self.push_ok else "fatal: could not read Username")
        if args[0] == "rev-parse":
            return GitResult(0, "abc1234")
        return GitResult(0, "")


def _prepare_ok():
    return "2026-09-25T21:00:00", {"match": 421, "player": 161, "session_note": 9, "memo": 8}


def test_pushed_when_db_changed():
    git = FakeGit(db_changed=True)
    out = syncer.run_sync(git=git, prepare_fn=_prepare_ok)
    assert out == {
        "status": "pushed", "commit": "abc1234", "stamp": "2026-09-25T21:00:00",
        "counts": {"match": 421, "player": 161, "session_note": 9, "memo": 8},
    }
    verbs = [c[0] for c in git.calls]
    assert verbs == ["add", "diff", "commit", "push", "rev-parse"]
    # ONLY the DB + stamp are committed — code in progress stays out.
    commit = git.calls[2]
    assert commit[-2:] == [syncer.DB_REL, syncer.STAMP_REL]
    assert "--" in commit and commit[commit.index("-m") + 1].startswith("DB sync 20")
    assert git.calls[3] == ["push", "origin", "master"]


def test_nothing_when_db_unchanged(monkeypatch):
    monkeypatch.setattr(syncer, "_read_stamp", lambda: "2026-09-25T20:13:49")
    git = FakeGit(db_changed=False)
    out = syncer.run_sync(git=git, prepare_fn=_prepare_ok)
    assert out["status"] == "nothing"
    assert out["stamp"] == "2026-09-25T20:13:49"  # the previous stamp, restored
    verbs = [c[0] for c in git.calls]
    # The fresh stamp is reverted; no commit, no push.
    assert verbs == ["add", "diff", "reset", "checkout"]
    assert git.calls[3] == ["checkout", "--", syncer.STAMP_REL]


def test_push_failure_is_reported():
    git = FakeGit(db_changed=True, push_ok=False)
    with pytest.raises(SyncError, match=r"(?s)git push failed.*could not read Username"):
        syncer.run_sync(git=git, prepare_fn=_prepare_ok)


def test_refused_in_share_mode(monkeypatch):
    monkeypatch.setattr(settings, "SHARE_MODE", True)
    with pytest.raises(SyncError, match="own machine"):
        syncer.run_sync(git=FakeGit(True), prepare_fn=_prepare_ok)


def test_endpoint_maps_results(client, monkeypatch):
    monkeypatch.setattr(syncer, "run_sync", lambda: {"status": "pushed", "commit": "abc1234",
                                                     "stamp": "2026-09-25T21:00:00", "counts": {}})
    assert client.post("/api/sync").json()["status"] == "pushed"

    def _boom():
        raise SyncError("git push failed (the commit is saved locally, try again):\nfatal: x")

    monkeypatch.setattr(syncer, "run_sync", _boom)
    res = client.post("/api/sync")
    assert res.status_code == 500
    assert res.json()["detail"].startswith("git push failed")

    # On the shared host the read-only guard stops it before the handler.
    monkeypatch.setattr(settings, "SHARE_MODE", True)
    assert client.post("/api/sync").status_code == 403
