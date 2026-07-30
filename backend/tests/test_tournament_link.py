"""Match ↔ tournament link: entry FK + round + auto-event + cell text."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tournament import schemas as t_schemas
from app.features.tournament import service as t_service
from app.features.tracker import schemas, service
from app.features.tracker.models import Match, Player


def _tournament_with_doubles(db, partner_id: int):
    return t_service.create_tournament(
        db,
        t_schemas.TournamentIn(
            name="BBTV Open",
            start_date=dt.date(2026, 8, 8),
            end_date=dt.date(2026, 8, 9),
            entries=[
                t_schemas.EntryIn(discipline="doubles", partner_id=partner_id),
            ],
        ),
    )


def test_match_links_to_entry_with_round_and_auto_event(client, db):
    cat = category_id(db, "tournament_match")
    anna = Player(name="Anna", points=1100)
    binh = Player(name="Bình", points=950)
    db.add_all([anna, binh])
    db.commit()
    entry_id = _tournament_with_doubles(db, binh.id).tournaments[0].entries[0].id

    # No explicit event → the tournament's name becomes the Event.
    r = client.post(
        "/api/tracker/matches",
        json={
            "date": "2026-08-08",
            "category_id": cat,
            "discipline": "doubles",
            "my_sets": 3,
            "opp_sets": 1,
            "opponent_id": anna.id,
            "partner_id": binh.id,
            "tournament_entry_id": entry_id,
            "round": "qf",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["round"] == "qf"
    assert out["tournament_entry_id"] == entry_id
    assert out["tournament_name"] == "BBTV Open"
    assert out["event_name"] == "BBTV Open"  # auto-filled

    # An explicit event wins over the auto default.
    r2 = client.post(
        "/api/tracker/matches",
        json={
            "date": "2026-08-08",
            "category_id": cat,
            "my_sets": 3,
            "opp_sets": 0,
            "opponent_id": anna.id,
            "tournament_entry_id": entry_id,
            "round": "group",
            "event_name": "Custom name",
        },
    )
    assert r2.json()["event_name"] == "Custom name"

    # Unknown round values are rejected.
    bad = client.post(
        "/api/tracker/matches",
        json={
            "date": "2026-08-08",
            "category_id": cat,
            "my_sets": 3,
            "opp_sets": 0,
            "round": "finals",
        },
    )
    assert bad.status_code == 422


def test_cell_text_puts_knockout_rounds_on_own_lines(db):
    """Group-stage matches keep the compact W(a,b) grouping; each knockout
    round gets its own 'QF: W(3-1)' line after them."""
    cat = category_id(db, "tournament_match")
    d = dt.date(2026, 8, 8)

    def _m(my, opp, round=None, order=0):
        return Match(
            date=d, category_id=cat, discipline="singles", best_of=5,
            my_sets=my, opp_sets=opp, is_nonplaying=False, order_index=order,
            round=round,
        )

    text = service.format_match_cell(
        [_m(3, 0, "group", 0), _m(3, 1, "group", 1), _m(3, 2, "qf", 2), _m(1, 3, "sf", 3)]
    )
    assert text.splitlines() == ["W(3-0,3-1)", "QF: W(3-2)", "SF: L(1-3)"]

    # Matches with no round at all behave exactly as before.
    assert service.format_match_cell([_m(3, 0)]) == "W(3-0)"
