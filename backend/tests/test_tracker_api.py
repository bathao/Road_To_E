"""HTTP-level tests for the tracker router (isolated test DB via get_db override)."""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.tracker.models import Activity


# ---------------------------------------------------------------- activities
def test_activity_upsert_update_delete_and_validation(client, db):
    cat = category_id(db, "train_with_coach")
    payload = {"date": "2026-07-01", "category_id": cat, "duration_minutes": 60}

    # Create.
    r = client.put("/api/tracker/activities", json=payload)
    assert r.status_code == 200
    created = r.json()
    assert created["duration_minutes"] == 60

    # Upsert: same (date, category) updates in place — no duplicate row.
    r = client.put("/api/tracker/activities", json={**payload, "duration_minutes": 90})
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert r.json()["duration_minutes"] == 90
    db.expire_all()
    assert db.query(Activity).count() == 1

    # Empty payload (no duration / note / package start) deletes the row.
    r = client.put("/api/tracker/activities", json={**payload, "duration_minutes": 0})
    assert r.status_code == 200
    assert r.json() is None
    db.expire_all()
    assert db.query(Activity).count() == 0

    # Negative duration is rejected by schema validation.
    r = client.put("/api/tracker/activities", json={**payload, "duration_minutes": -5})
    assert r.status_code == 422


# ---------------------------------------------------------------- matches
def test_match_validation_rejects_bad_literals_and_negative_sets(client, db):
    cat = category_id(db, "practice_match")
    base = {"date": "2026-07-01", "category_id": cat, "my_sets": 3, "opp_sets": 1}

    assert client.post("/api/tracker/matches", json={**base, "discipline": "triples"}).status_code == 422
    assert client.post("/api/tracker/matches", json={**base, "best_of": 4}).status_code == 422
    assert client.post("/api/tracker/matches", json={**base, "my_sets": -1}).status_code == 422


def test_match_update_moves_cell_and_reappends_order(client, db):
    """PUT /matches to another (date, category) cell must append AFTER that
    cell's existing matches — a duplicate order_index would scramble cell
    render order and the newest-first tie-breaks. Same-cell edits keep the
    original order_index. (This is the edit-in-place backend since 2026-08-02.)"""
    cat = category_id(db, "practice_match")
    base = {"category_id": cat, "discipline": "singles", "best_of": 5,
            "my_sets": 3, "opp_sets": 1}
    # Two matches already in the target cell (order 0 and 1)…
    for _ in range(2):
        assert client.post(
            "/api/tracker/matches", json={**base, "date": "2026-07-02"}
        ).status_code == 200
    # …and the one we'll move, alone in its own cell.
    moved = client.post(
        "/api/tracker/matches", json={**base, "date": "2026-07-01"}
    ).json()
    assert moved["order_index"] == 0

    # Same-cell edit (score only): order_index untouched.
    same = client.put(
        f"/api/tracker/matches/{moved['id']}",
        json={**base, "date": "2026-07-01", "my_sets": 3, "opp_sets": 2},
    )
    assert same.status_code == 200 and same.json()["order_index"] == 0

    # Cell move: lands after the target cell's existing rows.
    r = client.put(
        f"/api/tracker/matches/{moved['id']}",
        json={**base, "date": "2026-07-02"},
    )
    assert r.status_code == 200
    assert r.json()["order_index"] == 2
    week = client.get("/api/tracker/weeks", params={"start": "2026-06-29"}).json()
    cell = [m for m in week["matches"] if m["date"] == "2026-07-02"]
    assert sorted(m["order_index"] for m in cell) == [0, 1, 2]  # unique
    assert all(m["date"] != "2026-07-01" for m in week["matches"] if m["id"] == moved["id"])


def test_first_and_last_date_endpoints(client, db):
    """first-date = earliest of the four data sources; last-date = latest.
    Both None when the DB is empty."""
    assert client.get("/api/tracker/first-date").json()["date"] is None
    assert client.get("/api/tracker/last-date").json()["date"] is None

    cat = category_id(db, "practice_match")
    db.add_all([
        Activity(date=dt.date(2026, 6, 3), category_id=category_id(db, "train_with_coach"),
                 duration_minutes=60),
    ])
    db.commit()
    client.post(
        "/api/tracker/matches",
        json={"date": "2026-07-05", "category_id": cat, "discipline": "singles",
              "best_of": 5, "my_sets": 3, "opp_sets": 0},
    )
    assert client.get("/api/tracker/first-date").json()["date"] == "2026-06-03"
    assert client.get("/api/tracker/last-date").json()["date"] == "2026-07-05"


def test_valid_match_appears_in_week_response(client, db):
    cat = category_id(db, "practice_match")
    r = client.post(
        "/api/tracker/matches",
        json={"date": "2026-07-01", "category_id": cat,
              "discipline": "singles", "best_of": 5, "my_sets": 3, "opp_sets": 1},
    )
    assert r.status_code == 200
    match_id = r.json()["id"]

    week = client.get("/api/tracker/weeks", params={"start": "2026-06-29"})
    assert week.status_code == 200
    body = week.json()
    assert any(m["id"] == match_id for m in body["matches"])
    assert body["cells"][f"{cat}|2026-07-01"]["display"] == "W(3-1)"


# ---------------------------------------------------------------- players
def test_player_empty_name_rejected(client):
    assert client.post("/api/tracker/players", json={"name": ""}).status_code == 422
    assert client.post("/api/tracker/players", json={"name": "   "}).status_code == 422

    r = client.post("/api/tracker/players", json={"name": "  Anh Tuan  "})
    assert r.status_code == 200
    assert r.json()["name"] == "Anh Tuan"  # trimmed
