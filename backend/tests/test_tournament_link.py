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


def test_tournament_edit_keeps_linked_matches(db):
    """Review find 2026-08-09 (severe): PUT used to recreate every entry with
    a new id, silently orphaning all linked matches (no FK on the ALTER-added
    tournament_entry_id column) — labels, rounds and the derived placement
    bonus all vanished. Edits must reconcile entries by id instead."""
    cat = category_id(db, "tournament_match")
    anna = Player(name="Anna", points=1100)
    binh = Player(name="Bình", points=950)
    db.add_all([anna, binh])
    db.commit()
    resp = _tournament_with_doubles(db, binh.id)
    tid = resp.tournaments[0].id
    entry = resp.tournaments[0].entries[0]
    m = Match(
        date=dt.date(2026, 8, 8), category_id=cat, discipline="doubles",
        best_of=5, my_sets=3, opp_sets=1, is_nonplaying=False, order_index=0,
        opponent_id=anna.id, partner_id=binh.id,
        tournament_entry_id=entry.id, round="f",
    )
    db.add(m)
    db.commit()

    # Edit that keeps the entry (id echoed back) + adds a second one.
    out = t_service.update_tournament(
        db, tid,
        t_schemas.TournamentIn(
            name="BBTV Open RENAMED",
            start_date=dt.date(2026, 8, 8),
            end_date=dt.date(2026, 8, 9),
            entries=[
                t_schemas.EntryIn(id=entry.id, discipline="doubles",
                                  partner_id=binh.id),
                t_schemas.EntryIn(discipline="singles"),
            ],
        ),
    )
    t_out = next(t for t in out.tournaments if t.id == tid)
    assert [e.id for e in t_out.entries][0] == entry.id  # survived the edit
    assert len(t_out.entries) == 2 and t_out.entries[1].id != entry.id
    db.expire_all()
    linked = db.get(Match, m.id)
    assert linked.tournament_entry_id == entry.id
    # The derived facts still resolve (placement needs the link alive).
    assert t_out.entries[0].final_placement == "champion"
    assert t_out.entries[0].latest_round == "f"

    # Removing an entry from the payload still deletes it (explicit choice).
    out2 = t_service.update_tournament(
        db, tid,
        t_schemas.TournamentIn(
            name="BBTV Open RENAMED",
            start_date=dt.date(2026, 8, 8),
            entries=[t_schemas.EntryIn(id=entry.id, discipline="doubles",
                                       partner_id=binh.id)],
        ),
    )
    assert [e.id for e in next(t for t in out2.tournaments if t.id == tid).entries] == [entry.id]


def test_entry_latest_round_feeds_round_autoadvance(db):
    """EntryOut.latest_round(+won) = deepest decided round of the linked
    matches — the MatchEditor pre-picks the NEXT round after a knockout win,
    including on day 2 of a multi-day event (user request 2026-08-09)."""
    cat = category_id(db, "tournament_match")
    anna = Player(name="Anna", points=1100)
    binh = Player(name="Bình", points=950)
    db.add_all([anna, binh])
    db.commit()
    resp = _tournament_with_doubles(db, binh.id)
    entry_id = resp.tournaments[0].entries[0].id
    today = dt.date(2026, 8, 8)

    def _entry():
        ts = t_service.list_tournaments(db, today).tournaments
        return next(t for t in ts if t.name == "BBTV Open").entries[0]

    def _m(my, opp, round, order, date=dt.date(2026, 8, 8)):
        return Match(
            date=date, category_id=cat, discipline="doubles", best_of=5,
            my_sets=my, opp_sets=opp, is_nonplaying=False, order_index=order,
            opponent_id=anna.id, partner_id=binh.id,
            tournament_entry_id=entry_id, round=round,
        )

    # No matches yet → nothing derived.
    e = _entry()
    assert e.latest_round is None and e.latest_round_won is None

    # Group results (even wins) never advance past the group stage.
    db.add(_m(3, 0, "group", 0))
    db.commit()
    e = _entry()
    assert (e.latest_round, e.latest_round_won) == ("group", True)

    # Day-1 knockout win → the FE default becomes the NEXT round, and day 2
    # sees the same fact (derived from ALL linked matches, not one cell).
    db.add(_m(3, 2, "r16", 1))
    db.commit()
    e = _entry()
    assert (e.latest_round, e.latest_round_won) == ("r16", True)

    # A loss is terminal: the deepest round stays put, won=False.
    db.add(_m(1, 3, "r8", 0, date=dt.date(2026, 8, 9)))
    db.commit()
    e = _entry()
    assert (e.latest_round, e.latest_round_won) == ("r8", False)
