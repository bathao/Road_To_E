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

# Routers included by app.main (in order).
# NOTE: retired features keep their DB tables untouched (user data is never
# deleted): Tactical Playbook (2026-07, playbook_tactic) and Video Analysis /
# profile engine (2026-07-29, va_profile / va_report / va_trait / va_skill /
# va_skill_snapshot — head_coach still reads the player's name from va_profile).
FEATURE_ROUTERS = [
    tracker_router.router,
    training_router.router,
    head_coach_router.router,
    tournament_router.router,
]

# Idempotent seed callables run on startup.
SEED_FUNCS = [
    tracker_seed.seed_categories,
    training_seed.migrate,
    head_coach_seed.migrate,
    tournament_seed.migrate,
]


def run_seeds(db: Session) -> None:
    for fn in SEED_FUNCS:
        fn(db)
