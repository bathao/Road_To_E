"""Jump rope as a DAILY staple item (2026-09-05): appended to every open
session with the user's fixed "100+ jumps = done" target, never ramped, never
offered as a knee-safe swap, and counted like any other item (grid + report)."""
from __future__ import annotations

import datetime as dt

from app.features.training import program, service
from app.features.training.models import TrainingSession


def test_catalog_shape():
    ex = program.EXERCISES["jump_rope"]
    assert ex.kind == "reps"
    assert ex.target == {"reps": 100, "unit": "jumps"}
    assert "jump_rope" in program.DAILY_KEYS
    assert "jump_rope" in program.NO_RAMP_KEYS and "jump_rope" in program.NO_SWAP_KEYS
    for level in program.DAY_TEMPLATES.values():
        for keys in level.values():
            assert "jump_rope" not in keys
    assert program.how_to_for("jump_rope")


def test_target_never_ramps_but_staples_still_do():
    jr = program.EXERCISES["jump_rope"]
    gb = program.EXERCISES["gyro_ball"]
    for gday, bias in ((1, 0), (30, 0), (200, 3), (200, -2)):
        assert program.daily_target(jr, gday, bias) == {"reps": 100, "unit": "jumps"}
    assert program.daily_target(gb, 30, 0)["sec"] > gb.target["sec"]


def test_never_offered_as_a_swap():
    for key in ("single_leg_balance", "wall_pushup", "gentle_bounce", "wrist_curl"):
        assert "jump_rope" not in {e.key for e in program.alternatives_for(key, set())}


def test_open_session_carries_jump_rope_and_it_counts(client, db):
    today = client.get("/api/training/today").json()
    items = {it["exercise_key"]: it for it in today["items"]}
    assert "jump_rope" in items
    jr = items["jump_rope"]
    assert jr["target"] == {"reps": 100, "unit": "jumps"}
    assert jr["done"] is False
    # The two older staples are still there — jump rope was appended, not swapped in.
    assert {"gyro_ball", "thigh_lift_bottle"} <= set(items)

    out = client.post(
        f"/api/training/session/{today['level']}/{today['day_index']}/item/{jr['id']}",
        json={"done": True},
    ).json()
    assert out["done_count"] == 1
    assert next(it for it in out["items"] if it["exercise_key"] == "jump_rope")["done"]

    # A session materialised BEFORE jump rope existed picks it up on the next read.
    row = db.query(TrainingSession).filter_by(level=today["level"], day_index=today["day_index"]).one()
    for it in list(row.items):
        if it.exercise_key == "jump_rope":
            db.delete(it)
    db.commit()
    again = client.get("/api/training/today").json()
    assert "jump_rope" in {it["exercise_key"] for it in again["items"]}


def test_completed_session_shows_in_the_physical_day_map(client, db):
    today = client.get("/api/training/today").json()
    jr = next(it for it in today["items"] if it["exercise_key"] == "jump_rope")
    client.post(
        f"/api/training/session/{today['level']}/{today['day_index']}/item/{jr['id']}",
        json={"done": True},
    )
    d = dt.date.today()
    client.post(
        f"/api/training/session/{today['level']}/{today['day_index']}/complete",
        json={"pain": "none", "rpe": "easy", "done_on": d.isoformat()},
    )
    pm = service.physical_day_map(db, d, d)
    info = pm[d.isoformat()]
    assert info["done"] == 1 and info["total"] == today["total"]
    # Volume attribution: the coach's muscle_volume sees the jump-rope group.
    rep = client.get("/api/training/report").json()
    assert any(mv["muscle"] == "Calves, ankles, footwork rhythm" for mv in rep["muscle_volume"])
