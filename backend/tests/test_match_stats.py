"""build_match_stats: named-opponent-only analytics (the Profile tab's middle section, formerly Match Stats)."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker import service
from app.features.tracker.models import Match, Player


def _match(cat, date, my, opp, opponent_id=None, handicap=0):
    return Match(
        date=date, category_id=cat, discipline="singles", best_of=5,
        my_sets=my, opp_sets=opp, is_nonplaying=False, order_index=0,
        opponent_id=opponent_id, handicap=handicap,
    )


def test_build_match_stats_grouping_and_unnamed_exclusion(db):
    cat = category_id(db, "practice_match")
    # Levels derive from POINTS vs my rating (950 default): 1250 = above (E
    # band vs my G), 950 = equal. The stored label is frozen legacy.
    anna = Player(name="Anna", points=1250)
    binh = Player(name="Binh", points=950)
    db.add_all([anna, binh])
    db.commit()

    d = dt.date(2026, 6, 5)
    db.add_all([
        _match(cat, d, 3, 1, opponent_id=anna.id),                        # W vs above
        _match(cat, d + dt.timedelta(days=1), 2, 3, opponent_id=anna.id),  # L vs above
        _match(cat, d + dt.timedelta(days=5), 3, 0, opponent_id=binh.id),  # W vs equal
        _match(cat, d + dt.timedelta(days=6), 3, 0, opponent_id=None),     # unnamed
    ])
    db.commit()

    res = service.build_match_stats(
        db, dt.date(2026, 5, 1), dt.date(2026, 6, 30)
    )
    # Range is clamped to the June-2026 floor for this tab.
    assert res.date_from == service.MATCH_STATS_FLOOR

    # The unnamed match is excluded: 3 matches, 2W 1L.
    assert (res.overall.total, res.overall.wins, res.overall.losses) == (3, 2, 1)
    assert res.overall.sets_won == 8 and res.overall.sets_lost == 4
    assert res.overall.win_rate == 2 / 3

    # (by_level was removed 2026-07-29 — ELO already prices opponent
    # strength; the derived level lives on in the h2h record labels below.)

    # Head-to-head sorted by matches played (Anna 2, Binh 1).
    assert [(o.name, o.played) for o in res.singles_h2h] == [("Anna", 2), ("Binh", 1)]
    anna_rec = res.singles_h2h[0]
    assert (anna_rec.wins, anna_rec.losses) == (1, 1)
    assert anna_rec.last_result == "L"  # most recent vs Anna was the loss
    assert len(anna_rec.matches) == 2
    assert anna_rec.matches[0].result == "L"  # most recent first

    # Dropdown briefs cover every named opponent seen.
    assert {o.name for o in res.opponents} == {"Anna", "Binh"}


def test_build_match_stats_one_v_two_and_two_v_one(db):
    """1v2/2v1 are team-style matchups: they land in doubles_h2h (with their
    own discipline tag, never merged with real doubles) and have their own
    discipline filter values."""
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", points=1250)
    binh = Player(name="Binh", points=950)
    dave = Player(name="Dave", points=1000)
    db.add_all([anna, binh, dave])
    db.commit()

    d = dt.date(2026, 6, 5)
    ovt = _match(cat, d, 3, 1, opponent_id=anna.id)  # 1v2 W vs Anna & Binh
    ovt.discipline = "one_v_two"
    ovt.opponent2_id = binh.id
    tvo = _match(cat, d, 1, 3, opponent_id=anna.id)  # 2v1 L (+ Dave) vs Anna
    tvo.discipline = "two_v_one"
    tvo.partner_id = dave.id
    dbl = _match(cat, d, 3, 2, opponent_id=anna.id)  # doubles vs Anna + unnamed
    dbl.discipline = "doubles"
    db.add_all([ovt, tvo, dbl])
    db.commit()

    res = service.build_match_stats(db, dt.date(2026, 6, 1), dt.date(2026, 6, 30))
    assert res.overall.total == 3 and res.singles_h2h == []
    recs = {r.discipline: r for r in res.doubles_h2h}
    # Three separate matchups — the 2v1 vs Anna never merges with the
    # doubles vs Anna + unnamed opponent.
    assert len(res.doubles_h2h) == 3
    assert recs["one_v_two"].partner_id is None
    assert recs["one_v_two"].opp2_name == "Binh"
    assert recs["two_v_one"].partner_name == "Dave"
    assert recs["two_v_one"].opp2_id is None

    # The discipline filter isolates each format.
    only = service.build_match_stats(
        db, dt.date(2026, 6, 1), dt.date(2026, 6, 30), discipline="one_v_two"
    )
    assert only.overall.total == 1 and only.overall.wins == 1


def test_new_opponents_first_ever_meeting_only(db):
    """new_opponents counts people whose FIRST-EVER match vs me falls in the
    range: any earlier match disqualifies (even doubles / other filters),
    both opponent slots count, and count_new_opponents (the recap path)
    agrees with the tab."""
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", points=1250)   # met before the range
    binh = Player(name="Binh", points=950)    # first met in range (opp2 slot)
    cara = Player(name="Cara", points=700)    # first met in range
    db.add_all([anna, binh, cara])
    db.commit()

    d = dt.date(2026, 7, 10)
    old = _match(cat, dt.date(2026, 6, 5), 3, 1, opponent_id=anna.id)
    dbl = _match(cat, d, 3, 1, opponent_id=anna.id)  # doubles: Anna + Binh
    dbl.discipline = "doubles"
    dbl.opponent2_id = binh.id
    db.add_all([old, dbl, _match(cat, d + dt.timedelta(days=1), 1, 3, opponent_id=cara.id)])
    db.commit()

    res = service.build_match_stats(db, d, d + dt.timedelta(days=5))
    assert res.new_opponents == 2  # Binh + Cara; Anna was met in June
    assert {o.name for o in res.opponents if o.is_new} == {"Binh", "Cara"}
    assert service.count_new_opponents(db, d, d + dt.timedelta(days=5)) == 2

    # The singles filter narrows the in-range side (only Cara qualifies) but
    # "met before" still spans the whole history: Anna stays not-new.
    singles = service.build_match_stats(
        db, d, d + dt.timedelta(days=5), discipline="singles"
    )
    assert singles.new_opponents == 1
    assert {o.name for o in singles.opponents if o.is_new} == {"Cara"}

    # A later range where everyone is already known → zero.
    db.add(_match(cat, dt.date(2026, 7, 20), 3, 0, opponent_id=cara.id))
    db.commit()
    later = service.build_match_stats(db, dt.date(2026, 7, 20), dt.date(2026, 7, 25))
    assert later.new_opponents == 0 and all(not o.is_new for o in later.opponents)


def test_trend_form_is_rolling_not_per_day(db):
    """trend[].form = win rate of the last FORM_WINDOW decided matches ending
    at that bucket — not the bucket's own (noisy) win rate. It hides until
    FORM_MIN decided matches, skips ties, and matches before the range seed
    the window so the line doesn't restart at the range edge."""
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", points=950)
    db.add(anna)
    db.commit()

    d = dt.date(2026, 6, 5)
    db.add_all([
        _match(cat, d, 3, 0, opponent_id=anna.id),                        # W
        _match(cat, d, 3, 1, opponent_id=anna.id),                        # W
        _match(cat, d + dt.timedelta(days=1), 1, 3, opponent_id=anna.id),  # L
        _match(cat, d + dt.timedelta(days=2), 2, 2, opponent_id=anna.id),  # T
        _match(cat, d + dt.timedelta(days=3), 0, 3, opponent_id=anna.id),  # L
    ])
    db.commit()

    res = service.build_match_stats(
        db, d, d + dt.timedelta(days=3), unit="day"
    )
    forms = [b.form for b in res.trend]
    # Day 1: only 2 decided matches — below FORM_MIN, no form yet.
    assert forms[0] is None
    # Day 2: window W,W,L. Day 3 is a tie — window (and form) unchanged,
    # while the bucket's own win_rate is None.
    assert forms[1] == forms[2] == 2 / 3
    assert res.trend[2].win_rate is None
    # Day 4: window W,W,L,L.
    assert forms[3] == 0.5

    # A range starting mid-history is seeded by the earlier matches: its
    # first bucket already carries the full window instead of restarting.
    later = service.build_match_stats(
        db, d + dt.timedelta(days=3), d + dt.timedelta(days=3), unit="day"
    )
    assert later.trend[0].form == 0.5


def test_build_handicap_split_directions(db):
    """Level × handicap-direction win rates: +N = I give, -N = I receive,
    0 = even; empty cells are omitted; unnamed matches excluded."""
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", points=1250)  # above (derived from points)
    cara = Player(name="Cara", points=700)  # below (H band vs my G)
    db.add_all([anna, cara])
    db.commit()

    d = dt.date(2026, 6, 5)
    db.add_all([
        _match(cat, d, 3, 1, opponent_id=anna.id, handicap=-2),   # W vs above, receiving
        _match(cat, d, 3, 2, opponent_id=anna.id, handicap=-2),   # W vs above, receiving
        _match(cat, d, 1, 3, opponent_id=anna.id),                # L vs above, even
        _match(cat, d, 2, 3, opponent_id=cara.id, handicap=3),    # L vs below, giving
        _match(cat, d, 3, 0, opponent_id=cara.id),                # W vs below, even
        _match(cat, d, 3, 0, opponent_id=None, handicap=-2),      # unnamed -> excluded
    ])
    db.commit()

    res = service.build_handicap_split(db, dt.date(2026, 5, 1), dt.date(2026, 6, 30))

    assert res["above"]["receive"] == {
        "played": 2, "wins": 2, "losses": 0, "win_rate": 1.0
    }
    assert res["above"]["even"]["losses"] == 1
    assert res["below"]["give"] == {
        "played": 1, "wins": 0, "losses": 1, "win_rate": 0.0
    }
    assert res["below"]["even"]["wins"] == 1
    # No handicapped matches vs equal opponents -> the cells are omitted.
    assert res["equal"] == {}


def test_normalize_handicap_pattern():
    """Digits in any format -> "a-b-c"; uniform/empty collapse to None (the
    signed handicap int alone carries uniform ratios)."""
    assert service.normalize_handicap_pattern("202") == "2-0-2"
    assert service.normalize_handicap_pattern("2-3-2") == "2-3-2"
    assert service.normalize_handicap_pattern(" 4 3 4 ") == "4-3-4"
    assert service.normalize_handicap_pattern("222") is None
    assert service.normalize_handicap_pattern("2") is None
    assert service.normalize_handicap_pattern("") is None
    assert service.normalize_handicap_pattern(None) is None


def test_last_handicap_vs_returns_most_recent_singles(db):
    """Editor pre-fill: newest singles match vs the opponent wins (same-day
    ties broken by order_index); doubles and other opponents are ignored."""
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", level="above")
    binh = Player(name="Binh", level="equal")
    db.add_all([anna, binh])
    db.commit()

    d = dt.date(2026, 6, 5)
    db.add_all([
        _match(cat, d, 1, 3, opponent_id=anna.id, handicap=-2),
        _match(cat, d + dt.timedelta(days=3), 2, 3, opponent_id=binh.id, handicap=3),
    ])
    # Newest vs Anna: received 4-3-4 (avg 4 stored, pattern kept).
    m = _match(cat, d + dt.timedelta(days=9), 3, 2, opponent_id=anna.id, handicap=-4)
    m.handicap_pattern = "4-3-4"
    db.add(m)
    db.commit()

    latest = service.last_handicap_vs(db, anna.id)
    assert (latest.handicap, latest.handicap_pattern) == (-4, "4-3-4")
    assert service.last_handicap_vs(db, binh.id).handicap == 3
    assert service.last_handicap_vs(db, 9999) is None
