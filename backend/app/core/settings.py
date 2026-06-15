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

# Single shared local text/reasoning model, used by BOTH the Head Coach (Tier-2
# synthesis) and the Video/Technique Analysis tab (parsing pasted cloud analysis
# into structured findings + synthesising the skill ledger / profile). One model
# loaded once on the GPU. qwen3:14b fits a 16GB GPU comfortably (~9-10GB at Q4)
# and has a thinking mode for multi-source reasoning. Swap here to try a larger
# reasoner (e.g. gpt-oss:20b, qwen3:30b-a3b) if quality proves insufficient.
TEXT_MODEL = "qwen3:14b"
HEAD_COACH_MODEL = TEXT_MODEL

# Built frontend (Vite output). Served as the SPA in production.
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

APP_TITLE = "Table Tennis Coach"
