"""Feature registry.

This is the single place that wires tabs into the backend. Adding a new tab's
backend = create ``app/features/<feature>/`` and append its router + seed here.
Importing the feature modules also registers their ORM models on Base.metadata.
"""
from sqlalchemy.orm import Session

from app.features.head_coach import router as head_coach_router
from app.features.head_coach import seed as head_coach_seed
from app.features.playbook import router as playbook_router
from app.features.tracker import router as tracker_router
from app.features.tracker import seed as tracker_seed
from app.features.training import router as training_router
from app.features.training import seed as training_seed
from app.features.video_analysis import router as video_router
from app.features.video_analysis import seed as video_seed

# Routers included by app.main (in order).
FEATURE_ROUTERS = [
    tracker_router.router,
    playbook_router.router,
    video_router.router,
    training_router.router,
    head_coach_router.router,
]

# Idempotent seed callables run on startup.
SEED_FUNCS = [
    tracker_seed.seed_categories,
    video_seed.seed_profile,
    training_seed.migrate,
    head_coach_seed.migrate,
]


def run_seeds(db: Session) -> None:
    for fn in SEED_FUNCS:
        fn(db)
