"""Coach-package math: compute_coach_packages + coach_package_start_allowed."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker import service
from app.features.tracker.models import Activity

BASE = dt.date(2026, 6, 1)


def _add_session(db, coach_id, day_offset, package_start=False):
    db.add(
        Activity(
            date=BASE + dt.timedelta(days=day_offset),
            category_id=coach_id,
            duration_minutes=60,
            is_package_start=package_start,
        )
    )
    db.commit()


def test_coach_packages_numbering_used_remaining(db):
    coach_id = category_id(db, "train_with_coach")

    # No sessions at all: any day may open package #1.
    assert service.coach_package_start_allowed(db, BASE) is True

    # Sessions 1..10 (package #1 fills implicitly, no marker needed).
    for i in range(10):
        _add_session(db, coach_id, i)

    resp = service.compute_coach_packages(db)
    assert len(resp.packages) == 1
    p1 = resp.packages[0]
    assert (p1.number, p1.used, p1.remaining, p1.over) == (1, 10, 0, 0)
    assert p1.is_current is True and p1.status == "done"

    # Mid-package days (positions 2..10) may NOT start a new package...
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=4)) is False
    # ...but position 1 can (to allow un-marking), and position 11 can.
    assert service.coach_package_start_allowed(db, BASE) is True
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=10)) is True

    # Sessions 11..12; the 11th is flagged as the start of package #2.
    _add_session(db, coach_id, 10, package_start=True)
    _add_session(db, coach_id, 11)

    resp = service.compute_coach_packages(db)
    assert [p.number for p in resp.packages] == [1, 2]
    p1, p2 = resp.packages
    assert (p1.used, p1.remaining, p1.is_current) == (10, 0, False)
    assert (p2.used, p2.remaining, p2.over) == (2, 8, 0)
    assert p2.is_current is True and p2.status == "ok"
    assert p2.start_date == BASE + dt.timedelta(days=10)
    assert p2.end_date == BASE + dt.timedelta(days=11)

    # Position 1 of package #2 stays allowed; position 3 of package #2 is not.
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=10)) is True
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=12)) is False
