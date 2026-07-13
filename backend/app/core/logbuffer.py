"""In-memory ring buffer of recent log lines, for the dev log panel.

Keeps the last ~400 formatted log records in RAM (no file, no growth): enough
to see what happened during an AI generation — model resolve/fallback,
timings, sanitize drops, retries, tracebacks — without shipping a real log
pipeline. Attached to the root logger once at import from app.main.
"""
from __future__ import annotations

import logging
from collections import deque

_MAX_LINES = 400

_buffer: deque[str] = deque(maxlen=_MAX_LINES)


class _RingBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _buffer.append(self.format(record))
        except Exception:  # noqa: BLE001 — logging must never break the app
            pass


_handler = _RingBufferHandler(level=logging.INFO)
_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
)


def install() -> None:
    """Attach the ring buffer to the root logger (idempotent)."""
    root = logging.getLogger()
    if _handler not in root.handlers:
        root.addHandler(_handler)


def tail(limit: int = _MAX_LINES) -> list[str]:
    """The most recent log lines, oldest first."""
    lines = list(_buffer)
    return lines[-limit:]
