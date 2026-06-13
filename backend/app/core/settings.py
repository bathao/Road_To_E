"""Application paths and settings."""
from pathlib import Path

# backend/app/core/settings.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "tabletennis.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# Uploaded clips for the Video Analysis tab (raw media is gitignored).
VIDEOS_DIR = DATA_DIR / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Reference images of the user, for auto-identifying them in clips.
PROFILE_REFS_DIR = DATA_DIR / "profile_refs"
PROFILE_REFS_DIR.mkdir(parents=True, exist_ok=True)

# Local AI (Ollama) used by the Video Analysis tab. Ollama runs as a separate
# process and serves a GPU-backed vision-language model on this port.
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_VLM_MODEL = "qwen3-vl:8b"
# Text-only model used to synthesise the living profile summaries from traits.
DEFAULT_TEXT_MODEL = "qwen3:14b"

# Optional TrackNet-style ball-detection ONNX model (Phase 4 / NC1). When this
# file exists AND onnxruntime is importable, ball tracking uses the CNN; otherwise
# it falls back to a classical motion detector, and ball metrics simply degrade to
# "not available" when nothing is trackable. Never a hard dependency.
BALL_MODEL_PATH = DATA_DIR / "models" / "ball_tracknet.onnx"

# Trained YOLOv8-seg model for foreground table-ROI segmentation (reused from the
# video_studio_v3 project, fine-tuned by the user on many table examples). When
# present AND ultralytics imports, table detection uses it (far more accurate than
# classical colour segmentation); otherwise it falls back to colour contrast.
TABLE_ROI_MODEL_PATH = DATA_DIR / "models" / "roi_seg.pt"

# Built frontend (Vite output). Served as the SPA in production.
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

APP_TITLE = "Table Tennis Coach"
