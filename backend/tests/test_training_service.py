"""Training Center service: autoregulation, completion, substitution, report,
and the tracker-facing physical_day_map (cutover behaviour)."""
from __future__ import annotations

import datetime as dt

import pytest

from app.features.training import program, service
from app.features.training.models import TrainingState


# ---------------------------------------------------------------- autoregulate
def test_autoregulate_clamping(db):
    state = service.ensure_state(db)
    assert (state.intensity_bias or 0) == 0

    service._autoregulate(db, "strong", None)  # strong pain -> -2
    assert state.intensity_bias == -2
    service._autoregulate(db, "strong", None)  # floor: stays at -2
    assert state.intensity_bias == -2

    service._autoregulate(db, None, "easy")  # pain-free easy -> +1
    assert state.intensity_bias == -1
    service._autoregulate(db, "mild", None)  # mild pain -> -1
    assert state.intensity_bias == -2

    state.intensity_bias = 3
    db.commit()
    service._autoregulate(db, None, "easy")  # cap: stays at 3
    assert state.intensity_bias == 3
    service._autoregulate(db, None, "hard")  # hard but pain-free: hold
    assert state.intensity_bias == 3


# ---------------------------------------------------------------- complete
def test_complete_session_invalid_level_raises_and_404(db, client):
    with pytest.raises(ValueError):
        service.complete_session(db, "no_such_level", 1, None)
    with pytest.raises(ValueError):
        service.complete_session(db, "foundation", 0, None)

    r = client.post("/api/training/session/no_such_level/1/complete", json={})
    assert r.status_code == 404


def test_complete_session_done_on_backdating_and_future_clamp(db):
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)

    out = service.complete_session(db, "foundation", 1, "note",
                                   done_on=today + dt.timedelta(days=3))
    assert out.done_on == today  # future date clamped to today
    assert out.status == "done"

    out = service.complete_session(db, "foundation", 2, None, done_on=yesterday)
    assert out.done_on == yesterday  # backdating allowed


# ---------------------------------------------------------------- substitute
def test_substitute_item_accepts_offered_alt_rejects_arbitrary(db):
    session, _ = service.open_session(db)  # foundation day 1 (legs)
    items = sorted(session.items, key=lambda it: it.sort_order)
    item = items[0]
    in_session = {it.exercise_key for it in session.items}

    offered = program.alternatives_for(item.exercise_key, in_session)
    assert offered, "expected at least one knee-safe alternative"
    alt_key = offered[0].key

    out = service.substitute_item(db, session.id, item.id, alt_key)
    assert out is not None
    db.refresh(item)
    assert item.exercise_key == alt_key
    assert item.done is False

    # A real exercise that was NOT offered for this item (wrong day-type)...
    other = items[1]
    assert service.substitute_item(db, session.id, other.id, "plank") is None
    # ...and a completely unknown key are both rejected.
    assert service.substitute_item(db, session.id, other.id, "no_such_move") is None
    db.refresh(other)
    assert other.exercise_key != "plank"


# ---------------------------------------------------------------- report
def test_report_counts_sessions_and_muscle_volume(db):
    # Session 1 (foundation day 1): tick two items, complete today.
    s1, _ = service.open_session(db)
    items1 = sorted(s1.items, key=lambda it: it.sort_order)
    service.tick_item(db, s1.id, items1[0].id, True)
    service.tick_item(db, s1.id, items1[1].id, True)
    service.complete_session(db, "foundation", 1, None)

    # Session 2 (foundation day 2): tick one item, complete today.
    s2, _ = service.open_session(db)
    assert (s2.level, s2.day_index) == ("foundation", 2)
    items2 = sorted(s2.items, key=lambda it: it.sort_order)
    service.tick_item(db, s2.id, items2[0].id, True)
    service.complete_session(db, "foundation", 2, None)

    rep = service.report(db)
    assert rep.total_sessions_done == 2
    assert rep.sessions_last_7d == 2
    # muscle_volume aggregates exactly the done items, by muscle group.
    assert sum(mv.times for mv in rep.muscle_volume) == 3
    muscles = {mv.muscle for mv in rep.muscle_volume}
    expected = {program.EXERCISES[items1[0].exercise_key].muscle,
                program.EXERCISES[items1[1].exercise_key].muscle,
                program.EXERCISES[items2[0].exercise_key].muscle}
    assert muscles == expected
    assert rep.day_type_counts["legs"] == 1  # day 1 is a legs day
    assert rep.day_type_counts["core"] == 1  # day 2 is a core day


# ---------------------------------------------------------------- cutover
def test_physical_day_map_respects_cutover(db):
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    service.ensure_state(db)  # stamps cutover_date = today on first run
    assert db.get(TrainingState, 1).cutover_date == today

    # Done BEFORE the cutover -> excluded (legacy checklist owns that day).
    service.complete_session(db, "foundation", 1, None, done_on=yesterday)
    # Done ON the cutover, all items ticked -> included and yellow.
    s2, _ = service.open_session(db)
    for it in s2.items:
        service.tick_item(db, s2.id, it.id, True)
    service.complete_session(db, "foundation", 2, None, done_on=today)

    day_map = service.physical_day_map(db, yesterday, today)
    assert yesterday.isoformat() not in day_map
    info = day_map[today.isoformat()]
    assert info["done"] == info["total"] > 0
    assert info["is_yellow"] is True
    assert info["day_index"] == 2
