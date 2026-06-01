"""FastAPI entrypoint: wires feature routers and serves the built frontend.

All feature routers come from app.features.registry, so adding a tab's backend
never touches this file. Static responses are sent with no-cache headers so a
fresh build is always picked up by the browser.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.db import SessionLocal, init_db
from app.core.settings import APP_TITLE, FRONTEND_DIST
from app.features import registry

app = FastAPI(title=APP_TITLE)

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
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        registry.run_seeds(db)
    finally:
        db.close()


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
    """Serve the SPA. Unknown client routes fall back to index.html."""
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
