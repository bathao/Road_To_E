"""Application paths and settings."""
import os
from pathlib import Path

# backend/app/core/settings.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "tabletennis.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# Local AI (Ollama) — a separate process serving a GPU-backed model on this port.
OLLAMA_BASE_URL = "http://localhost:11434"

# Fallback text model (used when HEAD_COACH_MODEL isn't pulled in Ollama).
# qwen3:14b fits a 16GB GPU comfortably (~9-10GB at Q4).
TEXT_MODEL = "qwen3:14b"

# Head Coach verdict model. A/B-tested on the real bundle (2026-07-13,
# qwen3:14b vs gpt-oss:20b vs qwen3.5:9b): qwen3.5:9b won — best Vietnamese,
# best number-grounding (no unit hallucinations), correct metric/value tagging,
# uses the day notes, and it's the smallest of the three (6.6GB). qwen3:14b
# invented unit math ("4570 phút = 51h/tuần"); gpt-oss:20b mixed English and
# left `order` empty. If HEAD_COACH_MODEL isn't pulled in Ollama, the service
# falls back to TEXT_MODEL automatically (see head_coach.service.resolve_model).
HEAD_COACH_MODEL = "qwen3.5:9b"

# Built frontend (Vite output). Served as the SPA in production.
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

APP_TITLE = "Road To E"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


# Shared read-only deployment (2026-09-25): the same app, published on a free
# host (Render) so the real-life coach can watch the Daily Tracker / Profile /
# Journal tabs. SHARE_MODE=1 turns every mutating /api call into a 403, hides
# the other tabs in the GUI and skips the on-startup backup (the host's disk
# is ephemeral; the source of truth stays on this PC and is pushed via
# sync.bat). Never set on the local machine.
SHARE_MODE = _env_flag("SHARE_MODE")

# Optional access code for the shared view. When set, every /api call (except
# /api/health and /api/config) must carry it in the X-Share-Key header; the
# GUI asks for it once and remembers it in the browser.
SHARE_KEY = os.environ.get("SHARE_KEY", "").strip()

# Written by sync.bat right before the DB is committed; shown in the shared
# view's banner ("Last synced ..."). Tracked in git on purpose.
LAST_SYNC_PATH = DATA_DIR / "last_sync.txt"

# Public URL of the shared copy. The local GUI's "Sync to coach" button polls
# <url>/api/config after a push until the new last_sync shows up there.
SHARE_PUBLIC_URL = os.environ.get("SHARE_PUBLIC_URL", "https://road-to-e.onrender.com").rstrip("/")
