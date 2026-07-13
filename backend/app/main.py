"""FastAPI entrypoint: wires feature routers and serves the built frontend.

All feature routers come from app.features.registry, so adding a tab's backend
never touches this file. Static responses are sent with no-cache headers so a
fresh build is always picked up by the browser.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core import logbuffer
from app.core.db import SessionLocal, init_db
from app.core.settings import APP_TITLE, FRONTEND_DIST
from app.features import registry

# uvicorn only configures its own loggers; give the app's `app.*` loggers a
# root handler so seed migrations / LLM calls / swallowed errors are visible.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# Keep the recent lines in RAM for the dev log panel (GET /head-coach/debug).
logbuffer.install()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        registry.run_seeds(db)
    finally:
        db.close()
    yield


app = FastAPI(title=APP_TITLE, lifespan=lifespan)

# Allow the Vite dev server during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    # Vite assets are content-hashed (immutable) — safe to cache forever. Only
    # index.html & friends need no-store so a fresh build is always picked up.
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


# Feature routers (tracker, and future tabs).
for feature_router in registry.FEATURE_ROUTERS:
    app.include_router(feature_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------- serve frontend
_assets_dir = FRONTEND_DIST / "assets"
if _assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    """Serve the SPA. Real files in dist (e.g. favicon.svg) are served directly;
    unknown client routes fall back to index.html."""
    # Serve a real static file at the root of dist (favicon, manifest, …) when it
    # exists and stays inside dist (guard against path traversal).
    # Unknown /api/... paths must 404, not silently serve index.html.
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if full_path:
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            candidate.is_file()
            and FRONTEND_DIST.resolve() in candidate.parents
        ):
            return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        status_code=200,
        content={
            "message": "Frontend not built yet. Run start.bat or "
            "`npm run build` in frontend/.",
        },
    )
