"""build_stats' summary buckets (overall / singles / doubles / vs_pips).

These numbers feed the Daily Tracker summary cards and the coach bundle.
(The per-card match drill-down GET /stats/matches was removed 2026-08-02
with the Daily Tracker win-rate cards — the Profile tab owns match stats.)
"""
import datetime as dt

from app.features.tracker import service
from app.features.tracker.models import Match, Player

from conftest import category_id

D1 = dt.date(2026, 7, 27)
D2 = dt.date(2026, 7, 28)


def _match(cat, date, my=3, opp_sets=1, **kw):
    kw.setdefault("discipline", "singles")
    kw.setdefault("is_nonplaying", False)
    kw.setdefault("order_index", 0)
    return Match(
        date=date, category_id=cat, best_of=5, my_sets=my, opp_sets=opp_sets, **kw
    )


def test_build_stats_buckets(db):
    cat = category_id(db, "practice_match")
    pips = Player(name="Gai", points=1000, plays_pips=1)
    plain = Player(name="Thuong", points=950)
    db.add_all([pips, plain])
    db.commit()

    db.add_all([
        _match(cat, D1, opponent_id=pips.id),                      # singles vs pips, W
        _match(cat, D1, my=1, opp_sets=3, opponent_id=plain.id,
               order_index=1),                                     # singles, L
        _match(cat, D2, discipline="doubles", opponent_id=plain.id,
               opponent2_id=pips.id, partner_id=plain.id),         # doubles vs pips
        _match(cat, D2, is_nonplaying=True, nonplaying_label="Travel",
               order_index=1),                                     # never counted
        _match(cat, dt.date(2026, 6, 1), opponent_id=pips.id),     # out of range
    ])
    db.commit()

    stats = service.build_stats(db, D1, D2)
    assert stats.overall.total == 3  # nonplaying + out-of-range excluded
    assert stats.singles.total == 2
    assert stats.doubles.total == 1
    # vs_pips covers BOTH the singles match vs the pips player and the
    # doubles match where opponent2 plays pips.
    assert stats.vs_pips.total == 2
    assert (stats.vs_pips.wins, stats.vs_pips.losses) == (2, 0)
