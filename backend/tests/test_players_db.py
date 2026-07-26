"""Database tab: player points, list ordering, match counts, my-rating."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker import schemas, service
from app.features.tracker.models import Match, Player


def _match(cat, my=3, opp=1, **kw):
    kw.setdefault("discipline", "singles")
    return Match(
        date=dt.date(2026, 6, 5), category_id=cat, best_of=5,
        my_sets=my, opp_sets=opp, is_nonplaying=False, order_index=0, **kw,
    )


def test_players_db_ordering_counts_and_points_update(db):
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", level="above", points=1100)
    binh = Player(name="Binh", level="equal")           # unrated
    cara = Player(name="Cara", level="below", points=700)
    db.add_all([anna, binh, cara])
    db.commit()
    db.add_all([
        _match(cat, opponent_id=anna.id),
        _match(cat, opponent_id=anna.id),
        _match(cat, discipline="doubles", opponent_id=cara.id,
               opponent2_id=anna.id, partner_id=binh.id),
    ])
    db.commit()

    resp = service.list_players_db(db)
    # Rated first (points desc), unrated last.
    assert [r.name for r in resp.players] == ["Anna", "Cara", "Binh"]
    by_name = {r.name: r for r in resp.players}
    assert by_name["Anna"].matches_played == 3  # 2x opponent + 1x opponent2
    assert by_name["Binh"].matches_played == 1  # partner
    assert by_name["Binh"].points is None
    # Points must survive serialization (regression: player_to_out dropped
    # the field, so every entered rating vanished from the tab on reload).
    assert by_name["Anna"].points == 1100
    assert by_name["Cara"].points == 700

    # Points update via the normal player PUT payload.
    service.update_player(
        db, binh.id,
        schemas.PlayerIn(name="Binh", level="equal", plays_pips=False, points=950),
    )
    assert db.get(Player, binh.id).points == 950
    by_name = {r.name: r for r in service.list_players_db(db).players}
    assert by_name["Binh"].points == 950  # visible after a reload, not just in ORM

    # A payload WITHOUT points (e.g. the picker's pips toggle) keeps them.
    service.update_player(
        db, binh.id,
        schemas.PlayerIn(name="Binh", level="equal", plays_pips=True),
    )
    b = db.get(Player, binh.id)
    assert b.points == 950 and b.plays_pips is True


def test_player_level_column_is_frozen_legacy(db):
    """Since 2026-07-27 the relative label derives from points at read time
    (service.level_from_points); the stored column is never written again."""
    above = service.create_or_get_player(db, schemas.PlayerIn(name="Cao", points=1250))
    assert above.points == 1250
    assert db.get(Player, above.id).level == "equal"  # column default, untouched

    # Get-or-create: an existing name never has its rating overwritten.
    again = service.create_or_get_player(db, schemas.PlayerIn(name="Cao", points=800))
    assert again.id == above.id and again.points == 1250

    # Updates ignore the level field entirely, even when a client sends one.
    service.update_player(
        db, above.id, schemas.PlayerIn(name="Cao", level="below", plays_pips=True)
    )
    p = db.get(Player, above.id)
    assert p.level == "equal" and p.plays_pips is True and p.points == 1250

    # The derivation itself (vs my 950/G default rating).
    assert service.level_from_points(1250, 950) == "above"  # E vs G
    assert service.level_from_points(700, 950) == "below"  # H vs G
    assert service.level_from_points(1000, 950) == "equal"  # G vs G
    assert service.level_from_points(None, 950) == "unrated"


def test_my_rating_default_and_roundtrip(db):
    assert service.get_my_points(db) == 950  # seeded default (rank G)
    assert service.set_my_points(db, 985) == 985
    assert service.get_my_points(db) == 985
