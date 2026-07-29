"""Application paths and settings."""
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
