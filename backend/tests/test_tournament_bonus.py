"""Tournament placement bonus: a flat ELO add-on per final result.

The placement is NEVER input — it is DERIVED from the matches entered in the
grid (their tournament_entry_id + round): reach the final → champion or
runner-up by its result, lose the SF → shared 3rd, lose the QF →
quarterfinal (singles-only tier). The bonus is a replay step at the END of
the deciding match's day, so editing/deleting matches self-corrects.
"""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tournament import schemas as t_schemas
from app.features.tournament import service as t_service
from app.features.tracker import rating, service
from app.features.tracker.models import Match, Player

D = dt.date(2026, 8, 8)


def _tournament(db, *, discipline="singles", start=D, partner_id=None):
    resp = t_service.create_tournament(
        db,
        t_schemas.TournamentIn(
            name="BBTV Open",
            start_date=start,
            entries=[
                t_schemas.EntryIn(discipline=discipline, partner_id=partner_id)
            ],
        ),
    )
    return resp.tournaments[0].entries[0].id


def _add_match(db, cat, entry_id, *, round, my=3, opp=0, date=D, order=0,
               opponent_id=None):
    """A tournament-linked match. Default opponent None/unrated → the match
    itself never moves the ELO, isolating the bonus in the asserts."""
    db.add(Match(
        date=date, category_id=cat, discipline="singles", best_of=5,
        my_sets=my, opp_sets=opp, is_nonplaying=False, order_index=order,
        opponent_id=opponent_id, tournament_entry_id=entry_id, round=round,
    ))
    db.commit()


def test_bonus_table_matches_the_user_values():
    """The agreed table, all ten cells (user decision 2026-07-31)."""
    assert rating.placement_bonus("singles", "champion") == 70
    assert rating.placement_bonus("singles", "runner_up") == 50
    assert rating.placement_bonus("singles", "third") == 35
    assert rating.placement_bonus("singles", "quarterfinal") == 10
    assert rating.placement_bonus("doubles", "champion") == 35
    assert rating.placement_bonus("doubles", "runner_up") == 25
    assert rating.placement_bonus("doubles", "third") == 10
    assert rating.placement_bonus("team", "champion") == 30
    assert rating.placement_bonus("team", "runner_up") == 20
    assert rating.placement_bonus("team", "third") == 10
    assert rating.placement_bonus("singles", None) == 0
    assert rating.placement_bonus("doubles", "quarterfinal") == 0  # no such tier


def test_placement_derives_from_entered_rounds(db):
    """Deepest entered round decides: F won → champion; F lost → runner-up;
    SF lost → 3rd; QF lost → quarterfinal; group-only / still-alive → none."""
    cat = category_id(db, "tournament_match")
    entry = _tournament(db)

    # Group stage only → eliminated in groups, no placement.
    _add_match(db, cat, entry, round="group", my=3, opp=1)
    _add_match(db, cat, entry, round="group", my=1, opp=3, order=1)
    assert rating.derive_placements(db) == {}

    # Lost the QF → quarterfinal (singles: +10).
    _add_match(db, cat, entry, round="qf", my=2, opp=3, order=2)
    assert rating.derive_placements(db) == {entry: ("quarterfinal", D)}

    # Hypothetically won that QF instead… entering an SF loss overrides.
    _add_match(db, cat, entry, round="sf", my=1, opp=3, order=3)
    assert rating.derive_placements(db) == {entry: ("third", D)}

    # Reached the final: lost → runner-up; won (a later entry) → champion.
    _add_match(db, cat, entry, round="f", my=2, opp=3, order=4)
    assert rating.derive_placements(db) == {entry: ("runner_up", D)}
    _add_match(db, cat, entry, round="f", my=3, opp=2, order=5)
    assert rating.derive_placements(db) == {entry: ("champion", D)}


def test_won_round_without_the_next_warns_about_missing_data(client, db):
    """Tournaments are entered AFTER they finish (user 2026-07-31): a won
    knockout round with no later round = forgotten matches → no bonus + a
    data_warning the GUI surfaces on the entry chip."""
    cat = category_id(db, "tournament_match")
    entry = _tournament(db)

    # Group-only data never warns (group elimination is on points, not wins).
    _add_match(db, cat, entry, round="group", my=3, opp=0)
    assert rating.derive_warnings(db) == {}

    # Won the SF but no Final entered → warning, no placement, no bonus.
    _add_match(db, cat, entry, round="sf", my=3, opp=1, order=1)
    assert rating.derive_placements(db) == {}
    assert service.compute_my_rating(db).current == 950
    warn = rating.derive_warnings(db)[entry]
    assert "Semi-final" in warn and "Final" in warn
    e = client.get("/api/tournaments").json()["tournaments"][0]["entries"][0]
    assert e["data_warning"] == warn

    # A 0-0 unfinished final doesn't decide anything (still warned).
    _add_match(db, cat, entry, round="f", my=0, opp=0, order=2)
    assert rating.derive_placements(db) == {}
    assert entry in rating.derive_warnings(db)

    # A decided final resolves both the placement and the warning.
    _add_match(db, cat, entry, round="f", my=3, opp=2, order=3)
    assert rating.derive_placements(db) == {entry: ("champion", D)}
    assert rating.derive_warnings(db) == {}


def test_bonus_lands_after_the_deciding_days_matches(db):
    """Champion bonus is a replay step at the END of the final's day: after
    that day's matches, before any later match — and it is not a 'match'."""
    cat = category_id(db, "tournament_match")
    off = category_id(db, "official_match")
    equal = Player(name="Ngang", points=950)
    db.add(equal)
    db.commit()
    entry = _tournament(db)

    # Rated final (counts for ELO itself) + an ordinary match two days later.
    _add_match(db, cat, entry, round="f", my=3, opp=0, opponent_id=equal.id)
    db.add(Match(date=D + dt.timedelta(days=2), category_id=off,
                 discipline="singles", best_of=5, my_sets=3, opp_sets=0,
                 opponent_id=equal.id, is_nonplaying=False, order_index=0))
    db.commit()

    final, steps = rating.replay(db)
    assert [s.date for s in steps] == [D, D, D + dt.timedelta(days=2)]
    bonus = steps[1]
    assert (bonus.match_id, bonus.delta) == (None, 70.0)
    assert bonus.bonus_label == "BBTV Open — Champion"
    assert bonus.bonus_discipline == "singles"

    r = service.compute_my_rating(db)
    assert r.counted_matches == 2  # the bonus row is not a match
    assert r.current == round(final) > 950 + 70  # bonus + two wins


def test_bonus_respects_anchor_and_entry_discipline(db):
    cat = category_id(db, "tournament_match")

    # Tournament decided before the anchor (2026-07-27) never pays.
    old = _tournament(db, start=dt.date(2026, 7, 20))
    _add_match(db, cat, old, round="f", my=3, opp=0, date=dt.date(2026, 7, 20))
    assert service.compute_my_rating(db).current == 950

    # The ENTRY's discipline prices the bonus (doubles champion = +35), and
    # a doubles QF loss pays nothing (the tier exists only for singles).
    partner = Player(name="Cap", points=900)
    db.add(partner)
    db.commit()
    dbl = _tournament(db, discipline="doubles", partner_id=partner.id)
    _add_match(db, cat, dbl, round="f", my=3, opp=1)
    assert service.compute_my_rating(db).current == 985  # 950 + 35

    dbl2 = _tournament(db, discipline="doubles", partner_id=partner.id)
    _add_match(db, cat, dbl2, round="qf", my=1, opp=3, order=1)
    assert service.compute_my_rating(db).current == 985  # unchanged


def test_deleting_the_deciding_match_takes_the_bonus_back(db):
    cat = category_id(db, "tournament_match")
    entry = _tournament(db)
    _add_match(db, cat, entry, round="sf", my=1, opp=3)  # 3rd → +35
    assert service.compute_my_rating(db).current == 985

    db.query(Match).delete()
    db.commit()
    assert service.compute_my_rating(db).current == 950


def test_bonus_row_in_movers_and_derived_entry_echo(client, db):
    cat = category_id(db, "tournament_match")
    entry = _tournament(db)
    _add_match(db, cat, entry, round="f", my=3, opp=1)

    out = service.build_rating_breakdown(
        db, date_from=dt.date(2026, 8, 1), date_to=dt.date(2026, 8, 31)
    )
    assert out.total_delta == 70.0
    assert out.counted == 0  # the unrated final itself doesn't count
    assert len(out.movers) == 1
    row = out.movers[0]
    assert (row.match_id, row.delta) == (None, 70.0)
    assert row.bonus_label == "BBTV Open — Champion"

    # The entry echoes its DERIVED placement + points for the GUI chip.
    e = client.get("/api/tournaments").json()["tournaments"][0]["entries"][0]
    assert e["final_placement"] == "champion"
    assert e["bonus_points"] == 70
