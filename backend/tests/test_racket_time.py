"""Racket Time: coach + partner minutes + match sets × RACKET_MINUTES_PER_SET."""
from __future__ import annotations

import datetime as dt

from app.features.tracker import service
from app.features.tracker.models import Activity, Match

from conftest import category_id

DAY = dt.date(2026, 7, 9)


def _setup_day(db) -> None:
    coach = category_id(db, "train_with_coach")
    partner = category_id(db, "training_with_partner")
    serve = category_id(db, "serve")
    official = category_id(db, "official_match")
    db.add_all([
        Activity(date=DAY, category_id=coach, duration_minutes=60),
        Activity(date=DAY, category_id=partner, duration_minutes=30),
        # Serve practice does NOT count towards racket time (per spec).
        Activity(date=DAY, category_id=serve, duration_minutes=45),
        # 0-3 + 3-2 = 8 sets -> 40 minutes of match play.
        Match(date=DAY, category_id=official, my_sets=0, opp_sets=3),
        Match(date=DAY, category_id=official, my_sets=3, opp_sets=2),
        # Non-playing entries never count.
        Match(date=DAY, category_id=official, is_nonplaying=True,
              nonplaying_label="Travel", my_sets=0, opp_sets=0),
    ])
    db.commit()


def test_racket_minutes_by_day(db):
    _setup_day(db)
    cats = db.query(service.Category).all()
    training, playing = service.racket_minutes_by_day(
        cats,
        db.query(Activity).all(),
        db.query(Match).all(),
    )
    iso = DAY.isoformat()
    assert training[iso] == 90  # coach 60 + partner 30 (serve excluded)
    assert playing[iso] == 8 * service.RACKET_MINUTES_PER_SET


def test_week_and_stats_include_racket_time(db, client):
    _setup_day(db)
    iso = DAY.isoformat()

    week = client.get(f"/api/tracker/weeks?start={iso}&end={iso}").json()
    racket = next(c for c in week["categories"] if c["key"] == "racket_time")
    notes = next(c for c in week["categories"] if c["key"] == "notes")
    assert racket["type"] == "computed"
    assert racket["sort_order"] < notes["sort_order"]  # row sits above Notes
    cell = week["cells"][f"{racket['id']}|{iso}"]
    assert cell["display"] == "2 hour 10 mins"  # 90 + 40 minutes

    stats = client.get(f"/api/tracker/stats?from={iso}&to={iso}").json()
    assert stats["racket_minutes_training"] == 90
    assert stats["racket_minutes_matches"] == 40
    assert stats["racket_minutes_total"] == 130
