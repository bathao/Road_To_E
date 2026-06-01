"""Application paths and settings."""
from pathlib import Path

# backend/app/core/settings.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "tabletennis.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# Built frontend (Vite output). Served as the SPA in production.
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

APP_TITLE = "Table Tennis Coach"
APP_PORT = 8000
