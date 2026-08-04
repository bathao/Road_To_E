"""Tournament Record (Profile tab): past-tournament history, all derived.

Cards show general info + per-entry result (round reached / placement) and
W-L; the detail lists every entered match. Nothing is stored — everything
comes from the Daily Tracker matches linked via tournament_entry_id.
"""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tournament import schemas as t_schemas
from app.features.tournament import service as t_service
from app.features.tracker import rating
from app.features.tracker.models import Match, Player

TODAY = dt.date.today()
PLAYED = TODAY - dt.timedelta(days=10)  # a finished tournament
UPCOMING = TODAY + dt.timedelta(days=10)


def _tournament(db, *, name="BBTV Open", start=PLAYED, end=None,
                discipline="singles"):
    resp = t_service.create_tournament(
        db,
        t_schemas.TournamentIn(
            name=name,
            start_date=start,
            end_date=end,
            entries=[t_schemas.EntryIn(discipline=discipline)],
        ),
    )
    t = next(t for t in resp.tournaments if t.name == name)
    return t.id, t.entries[0].id


def _add_match(db, cat, entry_id, *, round, my=3, opp=0, date=PLAYED, order=0,
               opponent_id=None):
    db.add(Match(
        date=date, category_id=cat, discipline="singles", best_of=5,
        my_sets=my, opp_sets=opp, is_nonplaying=False, order_index=order,
        opponent_id=opponent_id, tournament_entry_id=entry_id, round=round,
    ))
    db.commit()


def test_round_reached_derivation(db):
    cat = category_id(db, "tournament_match")
    _, entry = _tournament(db)
    assert rating.derive_round_reached(db) == {}

    # Group stage only, lost the last one → stopped in groups.
    _add_match(db, cat, entry, round="group", my=3, opp=1)
    _add_match(db, cat, entry, round="group", my=1, opp=3, order=1)
    assert rating.derive_round_reached(db) == {entry: ("group", False)}

    # Lost the 1/16 → stopped there.
    _add_match(db, cat, entry, round="r16", my=2, opp=3, order=2)
    assert rating.derive_round_reached(db) == {entry: ("r16", False)}


def test_record_lists_past_only_newest_first(db):
    cat = category_id(db, "tournament_match")
    old_id, old_entry = _tournament(db, name="Old Cup", start=PLAYED - dt.timedelta(days=30))
    new_id, new_entry = _tournament(db, name="New Cup", start=PLAYED)
    _tournament(db, name="Future Cup", start=UPCOMING)
    _add_match(db, cat, old_entry, round="group", my=3, opp=1,
               date=PLAYED - dt.timedelta(days=30))
    _add_match(db, cat, new_entry, round="group", my=1, opp=3, date=PLAYED)

    out = t_service.build_record(db)
    assert [t.name for t in out.tournaments] == ["New Cup", "Old Cup"]
    assert all(t.name != "Future Cup" for t in out.tournaments)


def test_same_day_tournament_shows_immediately(db):
    """Entering results retires a tournament instantly (user 2026-08-01):
    a TODAY tournament is upcoming while empty, and flips to played — in the
    Daily Tracker list AND the Profile record — the moment matches go in."""
    cat = category_id(db, "tournament_match")
    _, entry = _tournament(db, name="Today Cup", start=TODAY)

    # No results yet → still upcoming, not in the record.
    assert t_service.build_record(db).tournaments == []
    listed = t_service.list_tournaments(db).tournaments[0]
    assert listed.played is False

    _add_match(db, cat, entry, round="f", my=3, opp=1, date=TODAY)
    out = t_service.build_record(db)
    assert [t.name for t in out.tournaments] == ["Today Cup"]
    rec = out.tournaments[0].entries[0]
    assert rec.entry.final_placement == "champion" and rec.wins == 1
    listed = t_service.list_tournaments(db).tournaments[0]
    assert listed.played is True
    # ...and the coach's upcoming view drops it (results are in).
    assert t_service.upcoming_for_coach(db) == []


def test_multi_day_tournament_survives_day_one_results(db):
    """Multi-day rule (user 2026-08-04): day-1 results must NOT retire the
    card — the strip and the coach keep tracking day 2. A match dated on the
    LAST day retires it. (Single-day behaviour is unchanged — covered by
    test_same_day_tournament_shows_immediately.)"""
    cat = category_id(db, "tournament_match")
    day1, day2 = TODAY, TODAY + dt.timedelta(days=1)
    _, entry = _tournament(db, name="Two Day Cup", start=day1, end=day2)

    # Day-1 results (group + 1/16) → still upcoming everywhere.
    _add_match(db, cat, entry, round="group", my=3, opp=0, date=day1)
    _add_match(db, cat, entry, round="r16", my=3, opp=1, date=day1, order=1)
    assert t_service.list_tournaments(db).tournaments[0].played is False
    assert t_service.build_record(db).tournaments == []
    assert len(t_service.upcoming_for_coach(db)) == 1

    # A match on the last day → retires: record picks it up, coach drops it.
    _add_match(db, cat, entry, round="r8", my=1, opp=3, date=day2, order=2)
    assert t_service.list_tournaments(db).tournaments[0].played is True
    assert [t.name for t in t_service.build_record(db).tournaments] == ["Two Day Cup"]
    assert t_service.upcoming_for_coach(db) == []


def test_multi_day_knocked_out_day_one_retires_after_end(db):
    """Knocked out on day 1 of a multi-day event (no last-day matches): the
    card stays upcoming through the event's remaining days — the event is
    still running — and retires once the last day has passed."""
    cat = category_id(db, "tournament_match")

    # Still running: started yesterday, ends TODAY, only day-1 results.
    _, entry = _tournament(db, name="Running Cup",
                           start=TODAY - dt.timedelta(days=1), end=TODAY)
    _add_match(db, cat, entry, round="group", my=0, opp=3,
               date=TODAY - dt.timedelta(days=1))
    assert t_service.list_tournaments(db).tournaments[0].played is False

    # Same shape but the event ended yesterday → retired by the date alone.
    _, entry2 = _tournament(db, name="Finished Cup",
                            start=TODAY - dt.timedelta(days=2),
                            end=TODAY - dt.timedelta(days=1))
    _add_match(db, cat, entry2, round="group", my=0, opp=3,
               date=TODAY - dt.timedelta(days=2), order=1)
    by_name = {t.name: t for t in t_service.list_tournaments(db).tournaments}
    assert by_name["Finished Cup"].played is True
    assert by_name["Running Cup"].played is False


def test_record_entry_aggregates_and_matches(db):
    cat = category_id(db, "tournament_match")
    db.add(Player(name="Trung"))
    db.commit()
    opp = db.query(Player).filter(Player.name == "Trung").first().id
    _, entry = _tournament(db)

    # 2 group wins, then lost the QF → W2-L1, stopped at the QF (no medal:
    # QF loss IS the singles bonus tier, so placement exists here).
    _add_match(db, cat, entry, round="group", my=3, opp=1, opponent_id=opp)
    _add_match(db, cat, entry, round="group", my=3, opp=2, order=1)
    _add_match(db, cat, entry, round="qf", my=1, opp=3, order=2, opponent_id=opp)

    out = t_service.build_record(db)
    rec = out.tournaments[0].entries[0]
    assert rec.wins == 2 and rec.losses == 1
    assert rec.round_reached == "qf" and rec.reached_won is False
    assert rec.entry.final_placement == "quarterfinal"
    assert len(rec.matches) == 3
    assert rec.matches[0].opponent_name == "Trung"
    assert rec.matches[2].round == "qf" and rec.matches[2].won is False


def test_record_entry_without_matches(db):
    _, entry = _tournament(db)
    out = t_service.build_record(db)
    rec = out.tournaments[0].entries[0]
    assert rec.round_reached is None and rec.matches == []
    assert rec.wins == 0 and rec.losses == 0


def test_record_champion_and_warning(db):
    cat = category_id(db, "tournament_match")
    _, entry = _tournament(db)
    _add_match(db, cat, entry, round="sf", my=3, opp=1)
    _add_match(db, cat, entry, round="f", my=3, opp=2, order=1)
    out = t_service.build_record(db)
    rec = out.tournaments[0].entries[0]
    assert rec.entry.final_placement == "champion"
    assert rec.round_reached == "f" and rec.reached_won is True
    assert rec.entry.data_warning is None

    # A WON deepest round with nothing after it → warning, no placement.
    _, entry2 = _tournament(db, name="Gap Cup")
    _add_match(db, cat, entry2, round="r16", my=3, opp=0)
    out = t_service.build_record(db)
    rec2 = next(t for t in out.tournaments if t.name == "Gap Cup").entries[0]
    assert rec2.entry.final_placement is None
    assert rec2.reached_won is True and rec2.entry.data_warning


def test_record_api_shape(db, client):
    cat = category_id(db, "tournament_match")
    _, entry = _tournament(db)
    _add_match(db, cat, entry, round="group", my=3, opp=1)

    resp = client.get("/api/tournaments/record")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["tournaments"]) == 1
    e = body["tournaments"][0]["entries"][0]
    assert e["round_reached"] == "group" and e["wins"] == 1
    assert e["matches"][0]["my_sets"] == 3
