"""Tournament CRUD, upcoming/past ordering, and the Head Coach view."""
from __future__ import annotations

import datetime as dt

import pytest

from app.features.tournament import schemas, service
from app.features.tracker.models import Player

TODAY = dt.date(2026, 7, 25)


def _payload(name: str, start: dt.date, entries=(), **kw) -> schemas.TournamentIn:
    return schemas.TournamentIn(
        name=name, start_date=start, entries=list(entries), **kw
    )


def test_crud_ordering_and_partner_resolution(db):
    binh = Player(name="Bình", level="equal")
    db.add(binh)
    db.commit()

    service.create_tournament(
        db,
        _payload(
            "Giải xa",
            TODAY + dt.timedelta(days=40),
            entries=[schemas.EntryIn(discipline="singles", division="hạng E")],
        ),
    )
    service.create_tournament(
        db,
        _payload(
            "Giải gần",
            TODAY + dt.timedelta(days=8),
            entries=[
                schemas.EntryIn(discipline="doubles", partner_id=binh.id),
                schemas.EntryIn(
                    discipline="team",
                    team_members="CLB X",
                    teammate_ids=[binh.id],
                ),
            ],
        ),
    )
    # Past tournament (single-day, yesterday).
    service.create_tournament(db, _payload("Giải cũ", TODAY - dt.timedelta(days=1)))

    resp = service.list_tournaments(db, today=TODAY)
    # Upcoming soonest-first, then past.
    assert [t.name for t in resp.tournaments] == ["Giải gần", "Giải xa", "Giải cũ"]

    near = resp.tournaments[0]
    assert near.entries[0].partner_name == "Bình"  # resolved from the pool
    assert near.entries[1].team_members == "CLB X"
    assert near.entries[1].teammate_names == ["Bình"]  # roster resolved too
    # Doubles keeps no team text/roster; team keeps no partner (see _apply).
    assert near.entries[0].team_members is None and near.entries[0].teammate_ids == []
    assert near.entries[1].partner_id is None

    # Update replaces entries wholesale.
    service.update_tournament(
        db,
        near.id,
        _payload(
            "Giải gần",
            TODAY + dt.timedelta(days=8),
            entries=[schemas.EntryIn(discipline="singles")],
        ),
    )
    resp = service.list_tournaments(db, today=TODAY)
    assert [e.discipline for e in resp.tournaments[0].entries] == ["singles"]

    resp = service.delete_tournament(db, near.id)
    assert [t.name for t in resp.tournaments] == ["Giải xa", "Giải cũ"]

    with pytest.raises(LookupError):
        service.update_tournament(db, 9999, _payload("x", TODAY))


def test_upcoming_for_coach_labels_and_horizon(db):
    binh = Player(name="Bình", level="equal")
    db.add(binh)
    db.commit()

    service.create_tournament(
        db,
        _payload(
            "Giải ABC",
            TODAY + dt.timedelta(days=8),
            location="Q7",
            level_limit="E F G",
            entries=[
                schemas.EntryIn(discipline="singles", division="hạng E"),
                schemas.EntryIn(discipline="doubles", partner_id=binh.id),
            ],
        ),
    )
    # Beyond the horizon and in the past: both excluded.
    service.create_tournament(db, _payload("Quá xa", TODAY + dt.timedelta(days=120)))
    service.create_tournament(db, _payload("Đã qua", TODAY - dt.timedelta(days=3)))
    # Multi-day tournament running right now: included with negative days_left.
    service.create_tournament(
        db,
        schemas.TournamentIn(
            name="Đang diễn ra",
            start_date=TODAY - dt.timedelta(days=1),
            end_date=TODAY + dt.timedelta(days=1),
        ),
    )

    up = service.upcoming_for_coach(db, today=TODAY, horizon_days=90)
    assert [u["name"] for u in up] == ["Đang diễn ra", "Giải ABC"]
    abc = up[1]
    assert abc["days_left"] == 8 and abc["location"] == "Q7"
    assert abc["level_limit"] == "E F G"
    assert abc["entries"] == ["đơn — hạng E", "đôi (đánh cặp với Bình)"]
    assert up[0]["days_left"] == -1  # running now
