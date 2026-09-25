"""Shared read-only view (2026-09-25).

One middleware + one config payload, both driven by ``app.core.settings``:

- ``SHARE_MODE`` -> any non-read request under /api/ is refused with 403, so
  the public copy of the app can never be edited (an edit there would be
  lost on the next deploy anyway and would only confuse the coach).
- ``SHARE_KEY`` -> /api calls must carry the code in ``X-Share-Key``;
  /api/health (the host's health check) and /api/config (the GUI must learn
  that a code is required) stay open.

Settings are read per request (not at import time) so tests can flip them
with monkeypatch.
"""
from __future__ import annotations

import datetime as dt
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core import settings

log = logging.getLogger(__name__)

READ_METHODS = {"GET", "HEAD", "OPTIONS"}
# Reachable without the access code: the host pings /api/health, and the GUI
# needs /api/config to know whether to show the code prompt at all.
OPEN_PATHS = {"/api/health", "/api/config"}
KEY_HEADER = "X-Share-Key"

READ_ONLY_DETAIL = "Read-only shared view: changes are disabled."
KEY_DETAIL = "Access code required."


async def share_guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        if settings.SHARE_MODE and request.method not in READ_METHODS:
            return JSONResponse(status_code=403, content={"detail": READ_ONLY_DETAIL})
        if settings.SHARE_KEY and path not in OPEN_PATHS:
            # Header for fetch() calls; ?key= for plain browser navigation
            # (the Excel/CSV export link) which cannot send a header.
            given = request.headers.get(KEY_HEADER) or request.query_params.get("key", "")
            if given != settings.SHARE_KEY:
                return JSONResponse(status_code=401, content={"detail": KEY_DETAIL})
    return await call_next(request)


def last_sync() -> str | None:
    """ISO timestamp written by sync.bat, or None when never synced /
    unreadable (a missing file must never break the GUI)."""
    try:
        raw = settings.LAST_SYNC_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw).isoformat(timespec="minutes")
    except ValueError:
        log.warning("unparseable last_sync.txt: %r", raw)
        return None


def config_payload() -> dict:
    return {
        "share_mode": settings.SHARE_MODE,
        "key_required": bool(settings.SHARE_KEY),
        # Shared host: when its data was published. Local: when the player
        # last pushed (the Sync button's "Last synced" line).
        "last_sync": last_sync(),
        # Local GUI polls this after a push; meaningless on the host itself.
        "share_url": None if settings.SHARE_MODE else settings.SHARE_PUBLIC_URL,
    }
