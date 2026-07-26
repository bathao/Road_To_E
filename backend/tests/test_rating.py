"""ELO Phase 1a: the user's dynamic rating, replayed from the anchor.

dR = 12 × t(kind) × m(margin) × (S − E); counted matches are SINGLES vs a
named RATED opponent with NO handicap, dated on/after the anchor
(2026-07-27 by default). Everything else is deferred, not counted.
"""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker import service
from app.features.tracker.models import Match, Player, Setting

D = dt.date(2026, 7, 28)  # first day after the default anchor with play


def _match(cat, opp, my=3, opp_sets=0, date=D, **kw):
    kw.setdefault("discipline", "singles")
    kw.setdefault("is_nonplaying", False)
    kw.setdefault("order_index", 0)
    return Match(
        date=date, category_id=cat, best_of=5, my_sets=my, opp_sets=opp_sets,
        opponent_id=opp, **kw,
    )


def test_rating_formula_kind_and_margin_multipliers(db):
    off = category_id(db, "official_match")
    prac = category_id(db, "practice_match")
    tour = category_id(db, "tournament_match")  # new kind seeds like the others
    equal = Player(name="Ngang", points=950)
    strong = Player(name="Manh", points=1200)
    db.add_all([equal, strong])
    db.commit()

    # No matches yet: current == anchor, default anchor date applies.
    r = service.compute_my_rating(db)
    assert (r.points, r.current, r.counted_matches) == (950, 950, 0)
    assert r.anchor_date == "2026-07-27"

    # Official 3-0 sweep vs equal: 12 × 1.0 × 1.25 × (1 − 0.5) = +7.5 → 957.5
    db.add(_match(off, equal.id, my=3, opp_sets=0))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 958 and r.counted_matches == 1
    assert r.points == 950  # the anchor itself never moves on its own

    # Practice 2-3 deciding-set loss vs equal (E ≈ 0.511 at 957.5):
    # 12 × 0.5 × 0.75 × (0 − 0.511) ≈ −2.3 → 955.2
    db.add(_match(prac, equal.id, my=2, opp_sets=3, order_index=1))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 955 and r.counted_matches == 2

    # Tournament 3-1 win (m = 1.0) vs +245-stronger (E ≈ 0.196):
    # 12 × 1.5 × 1.0 × 0.804 ≈ +14.5 → 969.7
    db.add(_match(tour, strong.id, my=3, opp_sets=1, order_index=2))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 970 and r.counted_matches == 3


def test_rating_skips_everything_out_of_scope(db):
    off = category_id(db, "official_match")
    equal = Player(name="Ngang", points=950)
    unrated = Player(name="ChuaRo")  # no points
    db.add_all([equal, unrated])
    db.commit()
    db.add_all([
        # Before the anchor date — user decision: old matches never count.
        _match(off, equal.id, date=dt.date(2026, 7, 26)),
        # Doubles missing partner/opponent2 (whole pair must be named+rated),
        # unrated opponent (deferred), no named opponent.
        _match(off, equal.id, discipline="doubles"),
        _match(off, unrated.id),
        _match(off, None),
        # Handicapped, both uniform and per-set pattern (Phase 1b).
        _match(off, equal.id, handicap=2),
        _match(off, equal.id, handicap=-1, handicap_pattern="2-0-2"),
        # Non-playing / no result recorded.
        _match(off, equal.id, is_nonplaying=True, nonplaying_label="Travel"),
        _match(off, equal.id, my=0, opp_sets=0),
    ])
    db.commit()
    r = service.compute_my_rating(db)
    assert (r.current, r.counted_matches) == (950, 0)


def test_rating_counts_doubles_at_full_weight(db):
    off = category_id(db, "official_match")
    partner = Player(name="DongDoi", points=1050)
    opp1 = Player(name="DoiThu1", points=1100)
    opp2 = Player(name="DoiThu2", points=900)
    unrated = Player(name="ChuaRo")
    db.add_all([partner, opp1, opp2, unrated])
    db.commit()

    # My team averages (950+1050)/2 = 1000, theirs (1100+900)/2 = 1000 —
    # even. Official 3-0 sweep counts like singles (d = 1, user decision):
    # 12 × 1.0 × 1.0 × 1.25 × (1 − 0.5) = +7.5.
    db.add(_match(off, opp1.id, discipline="doubles",
                  opponent2_id=opp2.id, partner_id=partner.id))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 958 and r.counted_matches == 1  # 957.5 rounds up

    # An unrated partner or a missing second opponent skips the match.
    db.add_all([
        _match(off, opp1.id, discipline="doubles", opponent2_id=opp2.id,
               partner_id=unrated.id, order_index=1),
        _match(off, opp1.id, discipline="doubles", partner_id=partner.id,
               order_index=2),
    ])
    db.commit()
    assert service.compute_my_rating(db).counted_matches == 1


def test_manual_edit_becomes_new_anchor(db):
    off = category_id(db, "official_match")
    equal = Player(name="Ngang", points=950)
    db.add(equal)
    db.commit()
    db.add(_match(off, equal.id))  # would be +7.5 when counted
    db.commit()

    # Push the anchor date past the match: the replay must exclude it.
    db.merge(Setting(key="my_points_date", value="2026-08-01"))
    db.commit()
    r = service.compute_my_rating(db)
    assert (r.current, r.counted_matches) == (950, 0)
    assert r.anchor_date == "2026-08-01"

    # A manual points edit re-anchors at TODAY (whatever the clock says).
    service.set_my_points(db, 1000)
    assert service.get_my_points(db) == 1000
    assert service.get_my_anchor_date(db) == dt.date.today()
    assert service.compute_my_rating(db).points == 1000
