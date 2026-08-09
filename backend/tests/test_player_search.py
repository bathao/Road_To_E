"""Picker search (service.list_players, user rules 2026-08-09):
diacritic-insensitive token matching + most-played-first ranking."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker import service
from app.features.tracker.models import Match, Player

TODAY = dt.date(2026, 8, 9)


def _m(cat, date, opp=None, opp2=None, partner=None, nonplaying=False):
    return Match(
        date=date, category_id=cat, discipline="singles", best_of=5,
        my_sets=3, opp_sets=0, is_nonplaying=nonplaying, order_index=0,
        opponent_id=opp, opponent2_id=opp2, partner_id=partner,
    )


def _names(db, q=""):
    return [p.name for p in service.list_players(db, q, today=TODAY)]


def test_search_matches_without_diacritics_any_token_order(db):
    db.add_all([
        Player(name="Tuấn gỗ"), Player(name="Anh Tuấn Gai"), Player(name="Lợi Phạm"),
    ])
    db.commit()

    assert set(_names(db, "tuan")) == {"Tuấn gỗ", "Anh Tuấn Gai"}
    assert _names(db, "go tuan") == ["Tuấn gỗ"]  # token-AND, order-free
    assert _names(db, "pham") == ["Lợi Phạm"]
    assert _names(db, "PHẠM") == ["Lợi Phạm"]  # folding applies to the query too
    assert _names(db, "xyz") == []


def test_search_ranks_word_prefix_above_substring_above_frequency(db):
    cat = category_id(db, "practice_match")
    oanh = Player(name="Oanh")
    hoang = Player(name="Hoàng Kim")
    db.add_all([oanh, hoang])
    db.commit()
    # Hoàng plays me often, Oanh never — but "oan" STARTS Oanh's name and
    # only sits mid-word in "Hoàng": prefix tier beats play count.
    db.add_all([_m(cat, TODAY - dt.timedelta(days=i), opp=hoang.id) for i in range(3)])
    db.commit()
    assert _names(db, "oan") == ["Oanh", "Hoàng Kim"]


def test_empty_query_lists_current_regulars_first(db):
    cat = category_id(db, "practice_match")
    partner = Player(name="Cường CLB")   # 2 RECENT matches, as my partner
    old = Player(name="Cường Q7")        # 3 matches, all past the 90-day window
    fresh = Player(name="Cường Mới")     # nonplaying rows only → counts nothing
    db.add_all([partner, old, fresh])
    db.commit()
    db.add_all(
        [_m(cat, TODAY - dt.timedelta(days=5), partner=partner.id),
         _m(cat, TODAY - dt.timedelta(days=6), opp2=partner.id)]
        + [_m(cat, TODAY - dt.timedelta(days=100 + i), opp=old.id) for i in range(3)]
        + [_m(cat, TODAY, opp=fresh.id, nonplaying=True)]
    )
    db.commit()

    # Recent regulars first (partner slots count too), then all-time count,
    # then name — same order with and without a query.
    assert _names(db) == ["Cường CLB", "Cường Q7", "Cường Mới"]
    assert _names(db, "cuong") == ["Cường CLB", "Cường Q7", "Cường Mới"]
