"""Shared read-only view (2026-09-25): SHARE_MODE blocks writes, SHARE_KEY
gates reads, /api/config tells the GUI which of the two applies."""
from __future__ import annotations

from app.core import settings


class _Sync:
    """Stand-in for LAST_SYNC_PATH (no filesystem: the sandboxed test run
    cannot create pytest's tmp dir). None = the file does not exist."""

    def __init__(self, text: str | None):
        self.text = text

    def read_text(self, encoding: str = "utf-8") -> str:
        if self.text is None:
            raise FileNotFoundError("last_sync.txt")
        return self.text


def test_local_mode_is_untouched(client, monkeypatch):
    monkeypatch.setattr(settings, "LAST_SYNC_PATH", _Sync(None))
    assert client.get("/api/config").json() == {
        "share_mode": False, "key_required": False, "last_sync": None,
        "share_url": settings.SHARE_PUBLIC_URL,
    }
    assert client.post("/api/tracker/memos", json={"text": "x"}).status_code == 200


def test_share_mode_refuses_every_write(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_MODE", True)
    monkeypatch.setattr(settings, "LAST_SYNC_PATH", _Sync("2026-09-25T20:15:33\n"))

    for method, path in [
        ("post", "/api/tracker/memos"),
        ("put", "/api/tracker/day-notes"),
        ("patch", "/api/tracker/memos/1"),
        ("delete", "/api/tracker/memos/1"),
    ]:
        kwargs = {} if method == "delete" else {"json": {"text": "x"}}
        res = getattr(client, method)(path, **kwargs)
        assert res.status_code == 403, (method, path)
        assert "Read-only" in res.json()["detail"]
    # Reads (and the health check) keep working.
    assert client.get("/api/tracker/memos").status_code == 200
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/config").json() == {
        "share_mode": True, "key_required": False, "last_sync": "2026-09-25T20:15",
        "share_url": None,
    }
    # Non-API paths (the SPA itself) are never touched by the guard.
    assert client.get("/").status_code == 200


def test_share_mode_without_sync_file(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_MODE", True)
    monkeypatch.setattr(settings, "LAST_SYNC_PATH", _Sync(None))
    assert client.get("/api/config").json()["last_sync"] is None
    monkeypatch.setattr(settings, "LAST_SYNC_PATH", _Sync("not a date"))
    assert client.get("/api/config").json()["last_sync"] is None


def test_share_key_gates_api_reads(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_MODE", True)
    monkeypatch.setattr(settings, "SHARE_KEY", "spin2win")
    # Open paths: the host's health check and the GUI's bootstrap call.
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/config").json()["key_required"] is True
    # Everything else needs the header: a wrong or missing code is a 401.
    assert client.get("/api/tracker/memos").status_code == 401
    assert client.get(
        "/api/tracker/memos", headers={"X-Share-Key": "nope"}
    ).status_code == 401
    assert client.get(
        "/api/tracker/memos", headers={"X-Share-Key": "spin2win"}
    ).status_code == 200
    # Plain navigation (export download) passes the code as ?key=.
    assert client.get("/api/tracker/memos?key=spin2win").status_code == 200
    assert client.get("/api/tracker/memos?key=nope").status_code == 401
    # The code never unlocks writes.
    assert client.post(
        "/api/tracker/memos", json={"text": "x"}, headers={"X-Share-Key": "spin2win"}
    ).status_code == 403
