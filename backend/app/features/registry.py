"""Feature registry.

This is the single place that wires tabs into the backend. Adding a new tab's
backend = create ``app/features/<feature>/`` and append its router + seed here.
Importing the feature modules also registers their ORM models on Base.metadata.
"""
from sqlalchemy.orm import Session

from app.features.head_coach import router as head_coach_router
from app.features.head_coach import seed as head_coach_seed
from app.features.tournament import router as tournament_router
from app.features.tournament import seed as tournament_seed
from app.features.tracker import router as tracker_router
from app.features.tracker import seed as tracker_seed
from app.features.training import router as training_router
from app.features.training import seed as training_seed
from app.features.video_analysis import router as video_router
from app.features.video_analysis import seed as video_seed

# Routers included by app.main (in order).
# NOTE: the Tactical Playbook feature was retired (2026-07) — its code is gone
# but the playbook_tactic table remains in the DB untouched (user data is
# never deleted). The video-analysis router stays: the Profile tab uses its
# profile/skills/traits endpoints (manual findings only; the paste-analysis UI
# was retired at the same time).
FEATURE_ROUTERS = [
    tracker_router.router,
    video_router.router,
    training_router.router,
    head_coach_router.router,
    tournament_router.router,
]

# Idempotent seed callables run on startup.
SEED_FUNCS = [
    tracker_seed.seed_categories,
    video_seed.seed_profile,
    training_seed.migrate,
    head_coach_seed.migrate,
    tournament_seed.migrate,
]


def run_seeds(db: Session) -> None:
    for fn in SEED_FUNCS:
        fn(db)
