"""Drill-down list behind the Analysis stat cards (GET /stats/matches).

The list must use the SAME filter as build_stats' summary buckets — a card
saying "4 matches" must open a list of exactly those 4."""
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


def test_stats_matches_buckets_match_build_stats(db):
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
               order_index=1),                                     # never listed
        _match(cat, dt.date(2026, 6, 1), opponent_id=pips.id),     # out of range
    ])
    db.commit()

    stats = service.build_stats(db, D1, D2)
    for bucket, expected in (
        ("overall", stats.overall.total),
        ("singles", stats.singles.total),
        ("doubles", stats.doubles.total),
        ("vs_pips", stats.vs_pips.total),
    ):
        listed = service.list_stats_matches(db, D1, D2, bucket)
        assert len(listed) == expected, bucket

    # vs_pips covers BOTH the singles match vs the pips player and the
    # doubles match where opponent2 plays pips.
    vs = service.list_stats_matches(db, D1, D2, "vs_pips")
    assert {(m.date.isoformat(), m.discipline) for m in vs} == {
        ("2026-07-27", "singles"),
        ("2026-07-28", "doubles"),
    }

    # Newest first (date desc, then order_index desc) + ELO annotation set.
    overall = service.list_stats_matches(db, D1, D2, "overall")
    assert [(m.date.isoformat(), m.order_index) for m in overall] == [
        ("2026-07-28", 0),
        ("2026-07-27", 1),
        ("2026-07-27", 0),
    ]
    assert all(m.elo_status is not None for m in overall)
