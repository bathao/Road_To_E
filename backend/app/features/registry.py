"""Feature registry.

This is the single place that wires tabs into the backend. Adding a new tab's
backend = create ``app/features/<feature>/`` and append its router + seed here.
Importing the feature modules also registers their ORM models on Base.metadata.
"""
from sqlalchemy.orm import Session

from app.features.tracker import router as tracker_router
from app.features.tracker import seed as tracker_seed

# Routers included by app.main (in order).
FEATURE_ROUTERS = [
    tracker_router.router,
]

# Idempotent seed callables run on startup.
SEED_FUNCS = [
    tracker_seed.seed_categories,
]


def run_seeds(db: Session) -> None:
    for fn in SEED_FUNCS:
        fn(db)
