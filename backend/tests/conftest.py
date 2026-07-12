"""Shared fixtures for the backend test suite.

HARD ISOLATION from the real database (backend/data/tabletennis.db):

- All tests run against a fresh in-memory SQLite engine (``sqlite://`` +
  StaticPool) built per test; tables come from ``Base.metadata.create_all``.
- API tests override the app's ``get_db`` dependency with sessions bound to
  that test engine.
- ``TestClient`` is deliberately used WITHOUT entering its context manager, so
  the app lifespan (``init_db`` + startup seeds against the real engine) never
  runs.
- An autouse guard additionally patches the real-DB startup entry points in
  ``app.main`` to raise, so any accidental invocation fails loudly instead of
  touching real data.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.base import Base
from app.core.db import get_db
from app.features import registry  # noqa: F401  — registers all ORM models on Base
from app.features.tracker import seed as tracker_seed
from app.features.tracker.models import Category


@pytest.fixture(autouse=True)
def _never_touch_real_db(monkeypatch):
    """Guard: the real-DB startup path must never run from a test."""
    import app.main as app_main

    def _blocked(*_args, **_kwargs):
        raise RuntimeError(
            "Attempted to use the real database startup path from a test. "
            "Tests must only use the in-memory test engine."
        )

    monkeypatch.setattr(app_main, "init_db", _blocked)
    monkeypatch.setattr(app_main, "SessionLocal", _blocked)


@pytest.fixture()
def engine():
    """A fresh, fully isolated in-memory SQLite engine with all tables."""
    eng = create_engine(
        "sqlite://",  # in-memory; StaticPool shares the one connection
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db(session_factory) -> Session:
    """A session on the TEST engine, with the tracker categories seeded."""
    session = session_factory()
    tracker_seed.seed_categories(session)  # seeds run against the test engine only
    yield session
    session.close()


@pytest.fixture()
def client(session_factory, db):
    """TestClient with get_db overridden to the test engine.

    NOTE: no ``with`` block on purpose — entering the TestClient context
    manager would run the app lifespan (init_db + seeds on the REAL engine).
    Plain request calls skip lifespan entirely.
    """
    from app.main import app as fastapi_app

    def _override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.pop(get_db, None)


def category_id(db: Session, key: str) -> int:
    """Id of a seeded tracker category by key (test helper)."""
    cat = db.query(Category).filter(Category.key == key).first()
    assert cat is not None, f"category {key!r} not seeded"
    return cat.id
