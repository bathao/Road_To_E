"""Knocked-out entries (user button 2026-08-15, driver: SGPP 15–16/08 —
lost both group matches day 1, but a group exit can't be derived from
results, so the user marks the entry eliminated).

Marking EVERY entry retires the tournament immediately (user follow-up same
day: "xóa luôn khỏi next tournament, cập nhật result vào tab Profile") —
exactly like entering a last-day result does: the card leaves the Daily
Tracker, the Profile record shows the derived result, the coach stops
planning around it. A partially-eliminated tournament stays live for the
surviving entries; only there does the card's ☠ chip offer a GUI undo.
"""
from __future__ import annotations

import datetime as dt

import pytest

from conftest import category_id
from app.features.head_coach.service import _week_ahead_lines
from app.features.tournament import schemas as t_schemas
from app.features.tournament import service as t_service
from app.features.tracker.models import Match

TODAY = dt.date.today()
TOMORROW = TODAY + dt.timedelta(days=1)


def _two_day_tournament(db, *, entries=("team",)):
    """A tournament running TODAY → TOMORROW (the SGPP shape)."""
    resp = t_service.create_tournament(
        db,
        t_schemas.TournamentIn(
            name="SGPP Cup",
            start_date=TODAY,
            end_date=TOMORROW,
            entries=[t_schemas.EntryIn(discipline=d) for d in entries],
        ),
    )
    t = next(t for t in resp.tournaments if t.name == "SGPP Cup")
    return t.id, [e.id for e in t.entries]


def _add_group_loss(db, entry_id, *, date=TODAY, order=0):
    cat = category_id(db, "tournament_match")
    db.add(Match(
        date=date, category_id=cat, discipline="singles", best_of=5,
        my_sets=0, opp_sets=3, is_nonplaying=False, order_index=order,
        tournament_entry_id=entry_id, round="group",
    ))
    db.commit()


def _listed(db, tid):
    return next(
        t for t in t_service.list_tournaments(db, TODAY).tournaments if t.id == tid
    )


def test_toggle_roundtrip_and_unknown_entry(db):
    tid, (entry,) = _two_day_tournament(db)
    out = t_service.set_entry_eliminated(db, entry, True)
    t = next(t for t in out.tournaments if t.id == tid)
    assert t.entries[0].eliminated is True
    out = t_service.set_entry_eliminated(db, entry, False)
    t = next(t for t in out.tournaments if t.id == tid)
    assert t.entries[0].eliminated is False
    with pytest.raises(LookupError):
        t_service.set_entry_eliminated(db, 99999, True)


def test_patch_endpoint_shape(client, db):
    tid, (entry,) = _two_day_tournament(db)
    r = client.patch(f"/api/tournaments/entries/{entry}", json={"eliminated": True})
    assert r.status_code == 200
    t = next(t for t in r.json()["tournaments"] if t["id"] == tid)
    assert t["entries"][0]["eliminated"] is True
    assert client.patch(
        "/api/tournaments/entries/99999", json={"eliminated": True}
    ).status_code == 404


def test_fully_eliminated_retires_immediately(db):
    """Every entry knocked out = the event is over for the player: the card
    flips to played on the spot (mid-event!), the Profile record shows the
    honest group-stage result, and the coach's upcoming view drops it —
    same lifecycle as entering a last-day result. Un-marking (API) brings
    it back while the event is still running."""
    tid, (entry,) = _two_day_tournament(db)
    _add_group_loss(db, entry)
    _add_group_loss(db, entry, order=1)
    assert _listed(db, tid).played is False  # day-1 results alone don't retire

    t_service.set_entry_eliminated(db, entry, True)
    assert _listed(db, tid).played is True
    rec = t_service.build_record(db, TODAY).tournaments[0]
    assert rec.entries[0].round_reached == "group"
    assert rec.entries[0].losses == 2
    assert t_service.upcoming_for_coach(db, TODAY) == []
    # ...so the coach's 7-day scaffold treats the remaining day as ordinary.
    assert "SGPP" not in _week_ahead_lines(
        t_service.upcoming_for_coach(db, TODAY), TODAY
    )

    t_service.set_entry_eliminated(db, entry, False)
    assert _listed(db, tid).played is False  # still running → back on the board


def test_future_tournament_never_retired_by_a_stray_mark(db):
    """The ☠ button only exists on running days, but the API could mark a
    FUTURE tournament's entries — that must not retire it off the board
    before it even starts. Once the event is running, the mark applies."""
    resp = t_service.create_tournament(
        db,
        t_schemas.TournamentIn(
            name="Next Month Cup",
            start_date=TODAY + dt.timedelta(days=20),
            entries=[t_schemas.EntryIn(discipline="singles")],
        ),
    )
    t = next(t for t in resp.tournaments if t.name == "Next Month Cup")
    t_service.set_entry_eliminated(db, t.entries[0].id, True)

    still = next(
        x for x in t_service.list_tournaments(db, TODAY).tournaments if x.id == t.id
    )
    assert still.played is False  # future event stays upcoming
    on_start_day = next(
        x
        for x in t_service.list_tournaments(
            db, TODAY + dt.timedelta(days=20)
        ).tournaments
        if x.id == t.id
    )
    assert on_start_day.played is True  # running + all out → retires


def test_partial_elimination_keeps_tournament_live(db):
    """Doubles knocked out but singles still in: the tournament stays
    upcoming for the surviving entry — only its own label is annotated for
    the coach (and the card's ☠ chip offers the GUI undo)."""
    tid, (e_team, e_singles) = _two_day_tournament(db, entries=("team", "singles"))
    t_service.set_entry_eliminated(db, e_team, True)

    assert _listed(db, tid).played is False
    tours = t_service.upcoming_for_coach(db, TODAY)
    labels = tours[0]["entries"]
    assert labels[0].endswith("ĐÃ BỊ LOẠI") and "ĐÃ BỊ LOẠI" not in labels[1]
    # The week scaffold keeps planning the running days (still competing).
    assert "SGPP" in _week_ahead_lines(tours, TODAY)


def test_form_edit_keeps_the_mark(db):
    """The tournament form's entry reconcile must not silently clear the
    flag (it reconciles by id; eliminated isn't part of the form)."""
    tid, (e_team, e_singles) = _two_day_tournament(db, entries=("team", "singles"))
    t_service.set_entry_eliminated(db, e_team, True)
    t_service.update_tournament(
        db, tid,
        t_schemas.TournamentIn(
            name="SGPP Cup renamed",
            start_date=TODAY,
            end_date=TOMORROW,
            entries=[
                t_schemas.EntryIn(id=e_team, discipline="team"),
                t_schemas.EntryIn(id=e_singles, discipline="singles"),
            ],
        ),
    )
    assert _listed(db, tid).entries[0].eliminated is True
    assert _listed(db, tid).entries[1].eliminated is False
