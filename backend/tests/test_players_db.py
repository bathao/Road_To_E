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
    # Appearances split by role: facing me vs on my side.
    assert by_name["Anna"].matches_vs == 3  # 2x opponent + 1x opponent2
    assert by_name["Anna"].matches_with == 0
    assert by_name["Binh"].matches_vs == 0
    assert by_name["Binh"].matches_with == 1  # partner
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


def test_player_rename_updates_history_and_blocks_duplicates(db):
    """Renaming a player (the 'entered before I knew their real name' flow):
    matches reference the player id, so history follows automatically; a
    rename INTO another player's name is rejected (needs a merge, not two
    identical rows)."""
    import pytest

    cat = category_id(db, "practice_match")
    mystery = Player(name="Bé Học Trò thầy Long", level="equal", points=1050)
    nam = Player(name="Nam", level="equal", points=1200)
    db.add_all([mystery, nam])
    db.commit()
    db.add(_match(cat, opponent_id=mystery.id))
    db.commit()

    out = service.update_player(
        db, mystery.id,
        schemas.PlayerIn(name="Trần Văn Long", plays_pips=False, points=1050),
    )
    assert out is not None and out.name == "Trần Văn Long"
    # History follows: the match's resolved opponent name is the new one.
    week = service.build_week(db, dt.date(2026, 6, 1))
    assert week.matches[0].opponent_name == "Trần Văn Long"

    # Renaming into an existing player's name (case-insensitive) is blocked...
    with pytest.raises(ValueError, match="already exists"):
        service.update_player(
            db, mystery.id, schemas.PlayerIn(name="nam", plays_pips=False)
        )
    # ...and nothing changed.
    assert db.get(Player, mystery.id).name == "Trần Văn Long"

    # Saving a player under their own (unchanged) name stays a no-op success.
    ok = service.update_player(
        db, nam.id, schemas.PlayerIn(name="Nam", plays_pips=True)
    )
    assert ok is not None and ok.name == "Nam"


def test_list_player_matches_any_slot_newest_first(db):
    """The Database tab drill-down: every match involving the player in ANY
    slot (opponent, opponent2, partner), newest first; other players' matches
    and nonplaying rows excluded."""
    cat = category_id(db, "practice_match")
    anna = Player(name="Anna", points=1100)
    binh = Player(name="Binh", points=950)
    db.add_all([anna, binh])
    db.commit()

    old = _match(cat, opponent_id=anna.id)                       # singles vs Anna
    old.date = dt.date(2026, 6, 3)
    dbl = _match(cat, discipline="doubles", opponent_id=binh.id,
                 opponent2_id=anna.id)                           # Anna as opp2
    tvo = _match(cat, discipline="two_v_one", opponent_id=binh.id,
                 partner_id=anna.id)                             # Anna as partner
    tvo.date = dt.date(2026, 6, 7)
    other = _match(cat, opponent_id=binh.id)                     # not Anna's
    skip = _match(cat, opponent_id=anna.id)
    skip.is_nonplaying = True
    db.add_all([old, dbl, tvo, other, skip])
    db.commit()

    out = service.list_player_matches(db, anna.id)
    assert [m.id for m in out] == [tvo.id, dbl.id, old.id]  # newest first
    # Names resolve for the modal's "with X vs Y" line; ELO status is tagged.
    assert out[0].partner_name == "Anna"
    assert all(m.elo_status is not None for m in out)

    # The Database-tab badges must equal the modal's per-role row counts —
    # both exclude nonplaying rows (regression: counts used to include them).
    anna_row = {r.name: r for r in service.list_players_db(db).players}["Anna"]
    assert anna_row.matches_vs == 2  # old + dbl (skip is nonplaying)
    assert anna_row.matches_with == 1  # tvo

    assert service.list_player_matches(db, 9999) == []


def test_my_rating_default_and_roundtrip(db):
    assert service.get_my_points(db) == 950  # seeded default (rank G)
    assert service.set_my_points(db, 985) == 985
    assert service.get_my_points(db) == 985
