"""Coach-package math + the coach roster (compute_coach_packages,
coach_package_start_allowed, list/create_coach, seed backfill).

Coaches (user 2026-08-15): every Train-with-Coach session is stamped with a
coach; coaches with counts_package=False (Phi Vũ — paid per session) never
consume the 10-session block. coach_id None (legacy) counts as the package
coach. Replaces the 2026-08-13 note-based "phi vu" rule.
"""
from __future__ import annotations

import datetime as dt

import pytest

from conftest import category_id
from app.features.tracker import schemas, seed as tracker_seed, service
from app.features.tracker.models import Activity

BASE = dt.date(2026, 6, 1)


def _coach(db, name, counts=True):
    return service.create_coach(
        db, schemas.CoachIn(name=name, counts_package=counts)
    )


def _seeded(db):
    """The two default coaches — the db fixture's seed_categories() runs
    migrate(), which creates them (exactly like a real startup)."""
    by_name = {c.name: c for c in service.list_coaches(db)}
    return by_name["Minh Thới"], by_name["Phi Vũ"]


def _add_session(db, cat_id, day_offset, package_start=False, note=None, coach=None):
    db.add(
        Activity(
            date=BASE + dt.timedelta(days=day_offset),
            category_id=cat_id,
            duration_minutes=60,
            is_package_start=package_start,
            note=note,
            coach_id=coach.id if coach else None,
        )
    )
    db.commit()


def test_coach_packages_numbering_used_remaining(db):
    cat = category_id(db, "train_with_coach")

    # No sessions at all: any day may open package #1.
    assert service.coach_package_start_allowed(db, BASE) is True

    # Sessions 1..10 (package #1 fills implicitly, no marker needed).
    for i in range(10):
        _add_session(db, cat, i)

    resp = service.compute_coach_packages(db)
    assert len(resp.packages) == 1
    p1 = resp.packages[0]
    assert (p1.number, p1.used, p1.remaining, p1.over) == (1, 10, 0, 0)
    assert p1.is_current is True and p1.status == "done"

    # Mid-package days (positions 2..10) may NOT start a new package...
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=4)) is False
    # ...but position 1 can (to allow un-marking), and position 11 can.
    assert service.coach_package_start_allowed(db, BASE) is True
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=10)) is True

    # Sessions 11..12; the 11th is flagged as the start of package #2.
    _add_session(db, cat, 10, package_start=True)
    _add_session(db, cat, 11)

    resp = service.compute_coach_packages(db)
    assert [p.number for p in resp.packages] == [1, 2]
    p1, p2 = resp.packages
    assert (p1.used, p1.remaining, p1.is_current) == (10, 0, False)
    assert (p2.used, p2.remaining, p2.over) == (2, 8, 0)
    assert p2.is_current is True and p2.status == "ok"
    assert p2.start_date == BASE + dt.timedelta(days=10)
    assert p2.end_date == BASE + dt.timedelta(days=11)

    # Position 1 of package #2 stays allowed; position 3 of package #2 is not.
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=10)) is True
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=12)) is False


def test_start_next_coach_package_flags_session_11(db):
    """The card's one-click action: with 12 sessions and no marker, session 11
    becomes the new package's start (sessions 12+ belong to the NEW package)."""
    cat = category_id(db, "train_with_coach")

    # Not over yet -> refused.
    for i in range(10):
        _add_session(db, cat, i)
    with pytest.raises(ValueError):
        service.start_next_coach_package(db)

    # Two sessions past the block size.
    _add_session(db, cat, 10)
    _add_session(db, cat, 11)

    resp = service.start_next_coach_package(db)
    assert [p.number for p in resp.packages] == [1, 2]
    p1, p2 = resp.packages
    assert (p1.used, p1.status, p1.is_current) == (10, "done", False)
    assert (p2.used, p2.remaining, p2.is_current) == (2, 8, True)
    assert p2.start_date == BASE + dt.timedelta(days=10)  # session 11's day

    # Idempotence guard: the new block only has 2 sessions -> refused again.
    with pytest.raises(ValueError):
        service.start_next_coach_package(db)


def test_per_session_coach_excluded_from_package(db):
    """Sessions with a counts_package=False coach never consume the block —
    they surface as a per-coach counter on the card instead."""
    cat = category_id(db, "train_with_coach")
    mt, pv = _seeded(db)

    for i in range(10):
        _add_session(db, cat, i, coach=mt)
    # Two per-session sessions after the block filled — without the rule
    # they'd read as sessions 11 and 12.
    _add_session(db, cat, 10, coach=pv)
    _add_session(db, cat, 11, coach=pv)

    resp = service.compute_coach_packages(db)
    assert len(resp.packages) == 1
    assert (resp.packages[0].used, resp.packages[0].status) == (10, "done")
    assert [(c.coach_name, c.sessions) for c in resp.non_package] == [("Phi Vũ", 2)]

    # A stamped package-coach session still counts (runs the block over).
    _add_session(db, cat, 12, coach=mt)
    resp = service.compute_coach_packages(db)
    assert (resp.packages[0].used, resp.packages[0].status) == (11, "over")

    # ★ on a per-session coach's session is ignored — it never opens a block.
    phi_vu_day = next(
        s for s in service._coach_sessions(db) if s.coach_id == pv.id
    )
    phi_vu_day.is_package_start = True
    db.commit()
    assert len(service.compute_coach_packages(db).packages) == 1

    # The renew action flags the 11th COUNTED session (day 12), skipping the
    # two per-session days in between.
    resp = service.start_next_coach_package(db)
    assert [p.used for p in resp.packages] == [10, 1]
    assert resp.packages[1].start_date == BASE + dt.timedelta(days=12)
    # Per-session days predate the new block's start -> counter resets.
    assert resp.non_package == []

    # Position math skips them too: day 13 would be position 2 of the new
    # block (not allowed); the new block's own start stays allowed.
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=13)) is False
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=12)) is True


def test_per_session_day_cannot_open_package(db):
    """A per-session coach's day must not be OFFERED the ★ either (its mark
    is a compute no-op — review 2026-08-15)."""
    cat = category_id(db, "train_with_coach")
    mt, pv = _seeded(db)
    for i in range(10):
        _add_session(db, cat, i, coach=mt)
    _add_session(db, cat, 10, coach=pv)  # would-be position 11

    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=10)) is False
    # A COUNTED 11th session on the next day is still offered the ★.
    _add_session(db, cat, 11, coach=mt)
    assert service.coach_package_start_allowed(db, BASE + dt.timedelta(days=11)) is True


def test_all_sessions_per_session_still_surface_on_card(db):
    """Every session per-session so far → no package exists, but the card
    counter must still show them (a mis-assigned FIRST session is exactly
    the case the counter exists for)."""
    cat = category_id(db, "train_with_coach")
    _, pv = _seeded(db)
    _add_session(db, cat, 0, coach=pv)
    _add_session(db, cat, 1, coach=pv)

    resp = service.compute_coach_packages(db)
    assert resp.packages == []
    assert [(c.coach_name, c.sessions) for c in resp.non_package] == [("Phi Vũ", 2)]


def test_coach_roster_create_and_dedupe(db):
    mt, _ = _seeded(db)  # the default roster comes from the seed
    _coach(db, "Coach Ba", counts=False)
    # Fold-compare: a diacritic-near-duplicate is rejected, like players.
    with pytest.raises(ValueError):
        _coach(db, "phi vu")
    with pytest.raises(ValueError):
        _coach(db, "COACH BA")
    names = [c.name for c in service.list_coaches(db)]
    assert names == ["Minh Thới", "Phi Vũ", "Coach Ba"]
    assert service.default_coach_id(db) == mt.id


def test_seed_backfill_stamps_legacy_sessions(db):
    """First restart after the feature ships: the seeded coaches exist and
    legacy sessions get coach_id from the retired note rule — "Phi Vũ" in
    the note (any spelling) → Phi Vũ, everything else → Minh Thới. Notes
    themselves are never modified. Idempotent."""
    cat = category_id(db, "train_with_coach")
    _add_session(db, cat, 0, note="giao bóng")
    _add_session(db, cat, 1, note="tập với PHI VU nè")
    _add_session(db, cat, 2)

    tracker_seed.migrate(db)

    coaches = {c.name: c for c in service.list_coaches(db)}
    assert coaches["Minh Thới"].counts_package is True
    assert coaches["Phi Vũ"].counts_package is False
    rows = sorted(service._coach_sessions(db), key=lambda a: a.date)
    assert [a.coach_id for a in rows] == [
        coaches["Minh Thới"].id, coaches["Phi Vũ"].id, coaches["Minh Thới"].id
    ]
    assert rows[1].note == "tập với PHI VU nè"  # note untouched

    # Second run: nothing to restamp (coach_id already set everywhere).
    rows[1].coach_id = coaches["Minh Thới"].id
    db.commit()
    tracker_seed.migrate(db)
    db.refresh(rows[1])
    assert rows[1].coach_id == coaches["Minh Thới"].id  # backfill didn't rerun


def test_upsert_activity_coach_stamping(client, db):
    """PUT /activities: names a coach → stored; omits it → new rows default
    to the package coach, edits keep the stored one; ★ with a per-session
    coach is stripped (it would be invisible to the package math); unknown
    coach → 400. Non-coach categories never carry a coach."""
    cat = category_id(db, "train_with_coach")
    mt, pv = _seeded(db)

    base = {"date": BASE.isoformat(), "category_id": cat, "duration_minutes": 60}
    # Omitted coach on a new row → package coach.
    r = client.put("/api/tracker/activities", json=base)
    assert r.json()["coach_id"] == mt.id
    # Explicit per-session coach + ★ → coach stored, ★ stripped.
    r = client.put(
        "/api/tracker/activities",
        json={**base, "coach_id": pv.id, "is_package_start": True},
    )
    assert r.json()["coach_id"] == pv.id
    assert r.json()["is_package_start"] is False
    # Edit with coach omitted → keeps Phi Vũ (not reset to the default).
    r = client.put("/api/tracker/activities", json={**base, "duration_minutes": 90})
    assert (r.json()["coach_id"], r.json()["duration_minutes"]) == (pv.id, 90)
    # Unknown coach -> 400.
    assert (
        client.put(
            "/api/tracker/activities", json={**base, "coach_id": 999}
        ).status_code
        == 400
    )
    # Non-coach category ignores the field.
    other = category_id(db, "training_with_partner")
    r = client.put(
        "/api/tracker/activities",
        json={"date": BASE.isoformat(), "category_id": other,
              "duration_minutes": 30, "coach_id": pv.id},
    )
    assert r.json()["coach_id"] is None
