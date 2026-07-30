"""ELO Phase 1a: the user's dynamic rating, replayed from the anchor.

dR = 12 × t(kind) × m(margin) × (S − E); counted matches are SINGLES vs a
named RATED opponent with NO handicap, dated on/after the anchor
(2026-07-27 by default). Everything else is deferred, not counted.
"""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker import rating, service
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


def test_rating_one_v_two_and_two_v_one(db):
    """User rule 2026-07-27: the solo side's ELO ×2 is for the COMPARISON
    only ("coi như 2 người tôi đánh với 2 người bên kia") — on the
    team-average scale the solo side = that player's own rating. The
    win/loss delta keeps the NORMAL magnitude, never doubled."""
    off = category_id(db, "official_match")
    opp1 = Player(name="DoiThu1", points=1000)
    opp2 = Player(name="DoiThu2", points=900)
    solo = Player(name="MotMinh", points=1000)
    partner = Player(name="DongDoi", points=1050)
    unrated = Player(name="ChuaRo")
    db.add_all([opp1, opp2, solo, partner, unrated])
    db.commit()

    # 1v2: me (950) alone vs a pair averaging (1000+900)/2 = 950 — an even
    # kèo. Official 3-0 sweep: the normal +7.5 → 957.5.
    db.add(_match(off, opp1.id, discipline="one_v_two", opponent2_id=opp2.id))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 958 and r.counted_matches == 1

    # 2v1: my team (957.5 + 1050)/2 ≈ 1003.75 vs the solo opponent's 1000
    # (he stands in for both members): E ≈ 0.505, official 3-0 sweep
    # 12 × 1.25 × 0.495 ≈ +7.4 → 964.9.
    db.add(_match(off, solo.id, discipline="two_v_one",
                  partner_id=partner.id, order_index=1))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 965 and r.counted_matches == 2

    # Missing/unrated second opponent (1v2) or partner (2v1) skips the match.
    db.add_all([
        _match(off, opp1.id, discipline="one_v_two", order_index=2),
        _match(off, opp1.id, discipline="two_v_one", order_index=3),
        _match(off, opp1.id, discipline="one_v_two",
               opponent2_id=unrated.id, order_index=4),
    ])
    db.commit()
    assert service.compute_my_rating(db).counted_matches == 2


def test_one_v_two_handicap_folds_at_full_value(db, monkeypatch):
    """Chấp in 1v2/2v1 uses the plain formula ("cũng như công thức bình
    thường"): the full ladder bonus on the receiving side's average — the
    same absolute /400 shift as a singles chấp, no doubles-style halving."""
    monkeypatch.setattr(rating, "HANDICAP_SCALE", 1.0)
    off = category_id(db, "official_match")
    opp1 = Player(name="DoiThu1", points=1100)
    opp2 = Player(name="DoiThu2", points=1100)
    db.add_all([opp1, opp2])
    db.commit()

    # Pair averages 1100; me 950 receiving 2-2-2 (+150) → exactly equalized
    # (E = 0.5). Official 3-0 sweep: 12 × 1.25 × 0.5 = +7.5.
    db.add(_match(off, opp1.id, discipline="one_v_two",
                  opponent2_id=opp2.id, handicap=-2))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 958 and r.counted_matches == 1


def test_handicap_scale_is_half(db):
    """User decision 2026-07-27 after the backtest: the ladder applies at
    HANDICAP_SCALE = 0.5 (2-2-2 → +75, 4-4-4 → +225, 5-5-5 → +300)."""
    assert rating.HANDICAP_SCALE == 0.5
    assert service.handicap_bonus(2, None) == 75
    assert service.handicap_bonus(5, None) == 300


def test_handicap_bonus_ladder_and_cap(db, monkeypatch):
    """The user's ladder (2026-07-26): each rung +50, 0-2-0 → 50 … 5-5-5 →
    600 max; formula form 25×s (s ≤ 6) / 50×s − 150 over the 3-set sum s.
    Pinned to scale 1.0 — the ladder SHAPE is what's under test here."""
    monkeypatch.setattr(rating, "HANDICAP_SCALE", 1.0)
    cases = [
        ((1, "0-2-0"), 50), ((1, "2-0-2"), 100), ((2, None), 150),
        ((2, "2-3-2"), 200), ((3, "3-2-3"), 250), ((3, None), 300),
        ((3, "3-4-3"), 350), ((4, "4-3-4"), 400), ((4, None), 450),
        ((4, "4-5-4"), 500), ((5, "5-4-5"), 550), ((5, None), 600),
        ((1, None), 75),          # uniform 1-1-1 sits between 0-2-0 and 2-0-2
        ((2, "4-2-0-2-4"), 210),  # free-digit custom: 5 sets, avg 2.4/set
        ((6, None), 600),         # beyond 5-5-5 clamps to the maximum
    ]
    for (h, pattern), expected in cases:
        assert service.handicap_bonus(h, pattern) == expected, (h, pattern)
    assert service.handicap_bonus(0, None) == 0.0


def test_rating_folds_handicap_at_full_value(db, monkeypatch):
    """User decision: the receiver gets the FULL ladder bonus — a big chấp
    can flip the receiver into favourite, and the ± consequences follow:
    win as chấp-favourite → small gain; lose as chấp-favourite → big loss.
    Pinned to scale 1.0 so the documented example numbers stay exact."""
    monkeypatch.setattr(rating, "HANDICAP_SCALE", 1.0)
    off = category_id(db, "official_match")
    strong = Player(name="Manh", points=1100)
    close = Player(name="Gan", points=1000)
    db.add_all([strong, close])
    db.commit()

    # Receiving 2-2-2 (+150) from a +150-stronger opponent: exactly
    # equalized (E = 0.5). Official 3-0 sweep: 12 × 1.25 × 0.5 = +7.5.
    db.add(_match(off, strong.id, handicap=-2))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 958 and r.counted_matches == 1

    # Receiving 4-4-4 (+450) from a barely-stronger opponent makes ME the
    # favourite (957.5 + 450 = 1407.5 vs 1000, E ≈ 0.91): winning a 3-0
    # sweep earns almost nothing — 12 × 1.25 × 0.087 ≈ +1.3.
    db.add(_match(off, close.id, handicap=-4, order_index=1))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 959 and r.counted_matches == 2

    # Same big chấp but LOSING 0-3 as the favourite: the full deduction —
    # 12 × 1.25 × −0.913 ≈ −13.7 ("được chấp nhiều mà thua thì xứng đáng
    # bị trừ nhiều điểm").
    db.add(_match(off, close.id, handicap=-4, my=0, opp_sets=3, order_index=2))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 945 and r.counted_matches == 3


def test_doubles_handicap_counts_for_one_member_only(db, monkeypatch):
    """User rule: in doubles the chấp ELO applies to ONE member — on the
    team-average scale that is half the ladder value. Pinned to scale 1.0."""
    monkeypatch.setattr(rating, "HANDICAP_SCALE", 1.0)
    off = category_id(db, "official_match")
    partner = Player(name="DongDoi", points=1050)
    opp1 = Player(name="DoiThu1", points=1100)
    opp2 = Player(name="DoiThu2", points=1100)
    db.add_all([partner, opp1, opp2])
    db.commit()

    # Team avg 1000 vs 1100; receiving 2-2-2 → ladder 150, halved to 75
    # (< gap 100, so the cap does not bite): mine 1075 vs 1100, E ≈ 0.464.
    # Official 3-0 sweep: 12 × 1.25 × (1 − 0.464) ≈ +8.0 → 958.
    db.add(_match(off, opp1.id, discipline="doubles", opponent2_id=opp2.id,
                  partner_id=partner.id, handicap=-2))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.current == 958 and r.counted_matches == 1


def test_rating_uses_at_match_time_snapshots(db):
    off = category_id(db, "official_match")
    vinh = Player(name="Vinh", points=1200)
    db.add(vinh)
    db.commit()

    m = _match(off, vinh.id, my=3, opp_sets=0)
    service.snapshot_match_points(db, m)
    assert m.opp_points_snap == 1200
    db.add(m)
    db.commit()
    before = service.compute_my_rating(db).current

    # Raising Vinh's static points later must NOT rewrite the old match —
    # the new value only applies to matches snapshotted from now on.
    vinh.points = 1400
    db.commit()
    assert service.compute_my_rating(db).current == before

    # Editing without changing the player keeps the original snapshot…
    service.snapshot_match_points(
        db, m, prev_ids=(m.opponent_id, m.opponent2_id, m.partner_id)
    )
    assert m.opp_points_snap == 1200
    # …changing the player in that slot re-snapshots at current points.
    other = Player(name="Khac", points=1000)
    db.add(other)
    db.commit()
    prev = (m.opponent_id, m.opponent2_id, m.partner_id)
    m.opponent_id = other.id
    service.snapshot_match_points(db, m, prev_ids=prev)
    assert m.opp_points_snap == 1000

    # A legacy row (no snapshot) falls back to the player's CURRENT points.
    db.add(_match(off, vinh.id, my=0, opp_sets=3, order_index=1))
    db.commit()
    r = service.compute_my_rating(db)
    assert r.counted_matches == 2  # snapshot row + legacy fallback row


def test_match_api_writes_snapshots(client, db):
    off = category_id(db, "official_match")
    vinh = Player(name="Vinh", points=1200)
    db.add(vinh)
    db.commit()
    r = client.post(
        "/api/tracker/matches",
        json={"date": "2026-07-28", "category_id": off, "discipline": "singles",
              "best_of": 5, "my_sets": 3, "opp_sets": 0, "opponent_id": vinh.id},
    )
    assert r.status_code == 200
    db.expire_all()
    m = db.get(Match, r.json()["id"])
    assert m.opp_points_snap == 1200 and m.partner_points_snap is None

    # Score-only edit keeps the snapshot even after the player's points move.
    vinh.points = 1400
    db.commit()
    r2 = client.put(
        f"/api/tracker/matches/{m.id}",
        json={"date": "2026-07-28", "category_id": off, "discipline": "singles",
              "best_of": 5, "my_sets": 3, "opp_sets": 2, "opponent_id": vinh.id},
    )
    assert r2.status_code == 200
    db.expire_all()
    assert db.get(Match, m.id).opp_points_snap == 1200


def test_week_elo_annotation(db):
    # (The /my-rating/history daily-curve endpoint was retired 2026-07-28 in
    # favour of build_rating_breakdown — covered by its own test below.)
    off = category_id(db, "official_match")
    equal = Player(name="Ngang", points=950)
    unrated = Player(name="ChuaRo")
    db.add_all([equal, unrated])
    db.commit()
    d1, d2 = dt.date(2026, 7, 28), dt.date(2026, 7, 29)
    win = _match(off, equal.id, date=d1)  # 3-0 sweep: +7.5 → 957.5
    loss = _match(off, equal.id, my=0, opp_sets=3, date=d2)  # −7.7 → ~949.8
    skip = _match(off, unrated.id, date=d2, order_index=1)  # unrated → tagged
    db.add_all([win, loss, skip])
    db.commit()

    week = service.build_week(db, dt.date(2026, 7, 27))
    by_id = {m.id: m for m in week.matches}
    assert by_id[win.id].elo_delta == 7.5
    assert by_id[win.id].elo_status == "counted"
    assert by_id[loss.id].elo_delta == -7.7
    assert by_id[skip.id].elo_delta is None
    assert by_id[skip.id].elo_status == "unrated"


def test_rating_breakdown_buckets_and_movers(db):
    """ELO-over-time aggregation: per-bucket net Δ + carry-forward rating on
    quiet days, None before the anchor, and every counted match as a mover."""
    off = category_id(db, "official_match")
    equal = Player(name="Ngang", points=950)
    strong = Player(name="Manh", points=1200)
    db.add_all([equal, strong])
    db.commit()
    d1, d2 = dt.date(2026, 7, 28), dt.date(2026, 7, 30)
    db.add_all([
        _match(off, equal.id, date=d1),  # sweep vs equal: +7.5 → 957.5
        # 2026-07-30: sweep loss vs equal (−7.7 → 949.8), then a 3-1 win
        # vs +250 (E ≈ 0.19, +9.7 → 959.5). Net for the day: +2.0.
        _match(off, equal.id, my=0, opp_sets=3, date=d2),
        _match(off, strong.id, my=3, opp_sets=1, date=d2, order_index=1),
    ])
    db.commit()

    b = service.build_rating_breakdown(
        db, dt.date(2026, 7, 26), dt.date(2026, 7, 31), unit="day"
    )
    by_day = {x.date_from.isoformat(): x for x in b.buckets}
    assert by_day["2026-07-26"].rating_end is None  # before the anchor
    assert by_day["2026-07-27"].rating_end == 950  # anchor day, no matches
    assert (by_day["2026-07-28"].delta, by_day["2026-07-28"].counted) == (7.5, 1)
    assert by_day["2026-07-29"].delta == 0  # quiet day carries the rating…
    assert by_day["2026-07-29"].rating_end == 958
    assert (by_day["2026-07-30"].delta, by_day["2026-07-30"].rating_end) == (2.0, 960)

    assert (b.rating_start, b.rating_end) == (950, 960)
    assert (b.total_delta, b.counted) == (9.5, 3)
    # Every counted match is a mover row, newest first (the GUI table's
    # default sort; other orders are client-side).
    assert [m.delta for m in b.movers] == [9.7, -7.7, 7.5]
    assert b.movers[0].opponent_name == "Manh"


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

    # Re-saving the UNCHANGED value must NOT move the anchor — an accidental
    # re-save would otherwise silently drop every replayed match.
    service.set_my_points(db, 950)
    assert service.get_my_anchor_date(db) == dt.date(2026, 8, 1)

    # A manual points edit re-anchors at TODAY (whatever the clock says).
    service.set_my_points(db, 1000)
    assert service.get_my_points(db) == 1000
    assert service.get_my_anchor_date(db) == dt.date.today()
    assert service.compute_my_rating(db).points == 1000
