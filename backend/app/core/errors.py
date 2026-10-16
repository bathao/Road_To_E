"""Typed service errors → one HTTP mapping (2026-10-16, REFACTOR.md Phase 2).

Services raise these instead of bare ``LookupError`` / ``ValueError``; the
handler installed by ``install`` turns them into ``{"detail": message}``
responses, so routers stop re-mapping exceptions by hand and every feature
answers the same way:

- ``NotFound``   → 404 (an id the client sent does not exist)
- ``Conflict``   → 409 (the request is valid but the current state refuses
                   it: a job already running, a reorder that lists a stale
                   id)
- ``BadRequest`` → 400 (the payload itself is wrong for this operation:
                   blank text, a note on a day with no coach session)

They subclass the built-ins they replace, so a router that still catches
``LookupError`` / ``ValueError`` keeps working while call sites migrate.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFound(AppError, LookupError):
    status_code = 404


class Conflict(AppError, ValueError):
    status_code = 409


class BadRequest(AppError, ValueError):
    status_code = 400


async def _handle(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def install(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle)
