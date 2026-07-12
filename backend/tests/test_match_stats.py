"""build_match_stats: named-opponent-only analytics (Match Stats tab)."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker import service
from app.features.tracker.models import Match, Player


def _match(cat, date, my, opp, opponent_id=None):
    return Match(
        date=date, category_id=cat, discipline="singles", best_of=5,
        my_sets=my, opp_sets=opp, is_nonplaying=False, order_index=0,
        opponent_id=opponent_id,
    )


def test_build_match_stats_grouping_and_unnamed_exclusion(db):
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", level="above")
    binh = Player(name="Binh", level="equal")
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

    by_level = {lr.level: lr.stats for lr in res.by_level}
    assert (by_level["above"].total, by_level["above"].wins, by_level["above"].losses) == (2, 1, 1)
    assert (by_level["equal"].total, by_level["equal"].wins) == (1, 1)
    assert by_level["below"].total == 0

    # Head-to-head sorted by matches played (Anna 2, Binh 1).
    assert [(o.name, o.played) for o in res.singles_h2h] == [("Anna", 2), ("Binh", 1)]
    anna_rec = res.singles_h2h[0]
    assert (anna_rec.wins, anna_rec.losses) == (1, 1)
    assert anna_rec.last_result == "L"  # most recent vs Anna was the loss
    assert len(anna_rec.matches) == 2
    assert anna_rec.matches[0].result == "L"  # most recent first

    # Dropdown briefs cover every named opponent seen.
    assert {o.name for o in res.opponents} == {"Anna", "Binh"}
