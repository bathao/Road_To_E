"""Match log (point-by-point charting): serve repertoire, points, set
scores, derived stats."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tactics import matchlog, schemas, seed as tactics_seed
from app.features.tactics.models import TacticServe
from app.features.tracker.models import Match, Player

D = dt.date(2026, 10, 10)


def _player(db, name):
    p = Player(name=name, level="equal", points=1100)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _match(db, opp_id, *, discipline="singles", my=2, o=3, order=0):
    m = Match(
        date=D, category_id=category_id(db, "tournament_match"), discipline=discipline,
        best_of=5, my_sets=my, opp_sets=o, is_nonplaying=False, order_index=order,
        opponent_id=opp_id, handicap=0,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _serve(h="me", spin="back", length="short", place="R", **extra):
    return {"h": h, "serve": True, "spin": spin, "length": length, "place": place, **extra}


def _shot(h, stroke, place="M"):
    return {"h": h, "stroke": stroke, "place": place}


def _point(client, match_id, server, shots, end_kind, set_no=1, forced=False, note=None):
    r = client.post(
        f"/api/tactics/matchlog/{match_id}/points",
        json={"set_no": set_no, "server": server, "shots": shots, "end_kind": end_kind,
              "forced": forced, "note": note},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_initial_serves_seed_once(db):
    assert tactics_seed.seed_serves(db) is True
    names = [s.name for s in matchlog.list_serves(db)]
    assert len(names) == 6 and names[0] == "Lệch phải · xoáy xuống ngắn phải"
    # Deleting one and re-running the seed must NOT bring it back.
    matchlog.delete_serve(db, matchlog.list_serves(db)[0].id)
    assert tactics_seed.seed_serves(db) is False
    assert db.query(TacticServe).count() == 5


def test_serve_crud(client):
    r = client.post("/api/tactics/serves", json={"name": "  Ngang dài  ", "spin": "side", "length": "long"})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["name"] == "Ngang dài"
    r = client.put(f"/api/tactics/serves/{sid}", json={"name": "Ngang dài trái", "spin": "side", "length": "long", "place": "L", "stance": "right"})
    assert r.json()["place"] == "L"
    assert client.post("/api/tactics/serves", json={"name": "x", "spin": "spiral", "length": "long"}).status_code == 422
    assert client.delete(f"/api/tactics/serves/{sid}").json() == {"ok": True}
    assert client.get("/api/tactics/serves").json() == []


def test_points_derive_winner_and_numbering(client, db):
    vy = _player(db, "Vy")
    m = _match(db, vy.id)
    p1 = _point(client, m.id, "me", [_serve(), _shot("opp", "bhpush"), _shot("me", "fhloop", "L")], "winner")
    assert (p1["point_no"], p1["winner"]) == (1, "me")
    p2 = _point(client, m.id, "me", [_serve(), _shot("opp", "fhloop", "R")], "error", note="  lỏng  ")
    assert (p2["point_no"], p2["winner"], p2["note"]) == (2, "me", "lỏng")  # opp missed → my point
    p3 = _point(client, m.id, "opp", [_serve("opp", "side"), {"h": "me", "stroke": "fhpush"}], "error")
    assert (p3["point_no"], p3["winner"]) == (3, "opp")  # I missed the push (no landing spot needed)
    # …but a shot that stayed in play must say where it landed.
    bad = client.post(f"/api/tactics/matchlog/{m.id}/points", json={
        "set_no": 1, "server": "opp", "shots": [_serve("opp"), {"h": "me", "stroke": "fhpush"}, _shot("opp", "other")], "end_kind": "error"})
    assert bad.status_code == 400
    p4 = _point(client, m.id, "opp", [_serve("opp", "side")], "winner")  # ace
    assert p4["winner"] == "opp"

    # Validation: first shot must be the server's serve; hitters alternate.
    bad = client.post(f"/api/tactics/matchlog/{m.id}/points", json={
        "set_no": 1, "server": "me", "shots": [_serve("opp")], "end_kind": "winner"})
    assert bad.status_code == 400
    bad = client.post(f"/api/tactics/matchlog/{m.id}/points", json={
        "set_no": 1, "server": "me", "shots": [_serve(), _shot("me", "fhloop")], "end_kind": "winner"})
    assert bad.status_code == 400

    # Delete the 2nd point → the 3rd and 4th renumber.
    assert client.delete(f"/api/tactics/matchlog/points/{p2['id']}").json() == {"ok": True}
    log = client.get(f"/api/tactics/matchlog/{m.id}").json()
    assert [p["point_no"] for p in log["points"]] == [1, 2, 3]
    assert log["opp_serves_seen"] == [
        {"stance": None, "motion": None, "spin": "side", "amount": None, "length": "short", "count": 2}
    ]


def test_sets_and_status(client, db):
    vy = _player(db, "Vy")
    m = _match(db, vy.id)
    dbl = _match(db, vy.id, discipline="doubles", order=1)
    r = client.put(f"/api/tactics/matchlog/{m.id}/sets", json={"sets": [
        {"set_no": 1, "my_points": 11, "opp_points": 8, "first_server": "me"},
        {"set_no": 2, "my_points": 7, "opp_points": 11},
    ]})
    assert [s["set_no"] for s in r.json()] == [1, 2]
    # Replace semantics.
    client.put(f"/api/tactics/matchlog/{m.id}/sets", json={"sets": [{"set_no": 1, "my_points": 11, "opp_points": 9}]})
    assert len(client.get(f"/api/tactics/matchlog/{m.id}").json()["sets"]) == 1
    _point(client, m.id, "me", [_serve()], "winner")
    assert client.get(f"/api/tactics/matchlog/status/{vy.id}").json() == [
        {"match_id": m.id, "points": 1, "sets_typed": 1}
    ]
    # A doubles match has no log.
    assert client.get(f"/api/tactics/matchlog/{dbl.id}").status_code == 404


def test_stats(client, db):
    vy = _player(db, "Vy")
    m = _match(db, vy.id)
    # Set 1, four points: my FH loop winner to L; my FH loop missed to L;
    # opp unforced error on a push after my serve; opp's BH loop winner.
    _point(client, m.id, "me", [_serve(serve_id=7), _shot("opp", "bhpush"), _shot("me", "fhloop", "L")], "winner")
    _point(client, m.id, "me", [_serve(serve_id=7), _shot("opp", "bhpush"), _shot("me", "fhloop", "L")], "error")
    _point(client, m.id, "opp", [_serve("opp", "side"), _shot("me", "flick", "R"), _shot("opp", "bhpush")], "error", forced=True)
    _point(client, m.id, "opp", [_serve("opp", "side"), _shot("me", "fhpush"), _shot("opp", "bhloop", "M")], "winner", note="đứng xa bàn")
    # Set 2: one long rally I win at 0-0.
    _point(client, m.id, "opp", [_serve("opp", "top", "long"), _shot("me", "block"), _shot("opp", "fhloop"),
                                  _shot("me", "block"), _shot("opp", "fhloop")], "error", set_no=2)

    s = client.get(f"/api/tactics/matchlog/{m.id}/stats").json()
    assert (s["matches"], s["points"], s["points_me"], s["points_opp"]) == (1, 5, 3, 2)
    assert s["on_my_serve"] == [2, 1] and s["on_opp_serve"] == [3, 2]
    assert s["attacks"] == {"fhloop": {"L": [1, 0, 1]}, "flick": {"R": [1, 0, 0]}}
    assert s["errors_me"] == {"fhloop": [1, 0]}
    assert s["errors_opp"] == {"bhpush": [0, 1], "fhloop": [1, 0]}
    assert s["winners_me"] == {"fhloop": 1} and s["winners_opp"] == {"bhloop": 1}
    assert s["receive_me"] == {"flick": [1, 0, 0], "fhpush": [0, 1, 0], "block": [1, 0, 0]}
    assert s["receive_opp"] == {"bhpush": [1, 1, 0]}  # won once (my loop missed), lost once
    assert s["rally_len"] == {"1-2": [0, 0], "3-4": [2, 2], "5+": [1, 0]}
    mine = [x for x in s["serves"] if x["side"] == "me"]
    assert mine == [{"side": "me", "serve_id": 7, "stance": None, "motion": None, "spin": "back",
                     "amount": None, "length": "short", "place": "R", "played": 2, "won": 1}]
    assert s["notes"][0]["score"] == "2–1" and s["notes"][0]["note"] == "đứng xa bàn"

    # Per-opponent aggregate = same numbers here (one charted match).
    assert client.get(f"/api/tactics/stats/{vy.id}").json()["points"] == 5

    # The coach prompt context carries the numbers (Vietnamese, facts only).
    from app.features.tactics.service import build_context
    ctx = build_context(db, db.get(Player, vy.id))
    assert "THỐNG KÊ TỪNG ĐIỂM" in ctx
    assert "giật phải: qua trái 1/0/1" in ctx
    assert "Đỡ giao bóng của học trò" in ctx and "gò phải 0/1/0" in ctx
    assert "đứng xa bàn" in ctx


def test_context_without_charting_has_no_block(db):
    from app.features.tactics.service import build_context
    vy = _player(db, "Vy")
    _match(db, vy.id)
    assert "THỐNG KÊ TỪNG ĐIỂM" not in build_context(db, db.get(Player, vy.id))
