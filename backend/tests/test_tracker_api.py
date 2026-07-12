"""HTTP-level tests for the tracker router (isolated test DB via get_db override)."""
from __future__ import annotations

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
