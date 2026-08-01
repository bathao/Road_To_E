"""Coach recaps: rolling 7/30-day windows, button-only generation."""
from __future__ import annotations

import datetime as dt

from app.features.head_coach import service as hc_service
from app.features.head_coach.models import HeadCoachRecap
from app.features.tracker.models import Activity, Match, Player

from conftest import category_id

# A fixed reference "today" so window math is deterministic.
TODAY = dt.date(2026, 8, 1)
WEEK_START = TODAY - dt.timedelta(days=6)  # last 7 days: Jul 26 → Aug 1
MONTH_START = TODAY - dt.timedelta(days=29)  # last 30 days: Jul 3 → Aug 1


def _fake_recap(*_args, **_kwargs) -> dict:
    return {
        "headline": "Giai đoạn ổn.",
        "overall": "Khối lượng giữ được, số trận tăng.",
        "went_well": ["Đánh 2 trận"],
        "concerns": ["Ít thể lực"],
        "focus_next": ["Thêm 1 buổi thể lực"],
    }


def _latest(db):
    """The production read path: newest generated week recap."""
    return hc_service.get_recaps(db, "week").latest


def _seed_day(db, day: dt.date, minutes: int = 60, matches: int = 0) -> None:
    coach = category_id(db, "train_with_coach")
    official = category_id(db, "official_match")
    if minutes:
        db.add(Activity(date=day, category_id=coach, duration_minutes=minutes))
    for i in range(matches):
        # Alternate W/L: even i wins 3-1, odd i loses 1-3.
        w = i % 2 == 0
        db.add(
            Match(
                date=day,
                category_id=official,
                my_sets=3 if w else 1,
                opp_sets=1 if w else 3,
            )
        )
    db.commit()


# ------------------------------------------------------------------ read side
def test_get_recaps_is_read_only(db):
    _seed_day(db, TODAY)  # data exists, but GET must never create/generate
    out = hc_service.get_recaps(db, "week")
    assert out.latest is None
    assert db.query(HeadCoachRecap).count() == 0


def test_get_recaps_returns_newest(db, monkeypatch):
    monkeypatch.setattr(hc_service, "_call_recap_model", _fake_recap)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")
    _seed_day(db, TODAY - dt.timedelta(days=1))
    _seed_day(db, TODAY)
    old = hc_service.start_recap(db, "week", today=TODAY - dt.timedelta(days=1))
    hc_service.run_recap_job(old.id, db)
    new = hc_service.start_recap(db, "week", today=TODAY)
    hc_service.run_recap_job(new.id, db)

    out = hc_service.get_recaps(db, "week")
    assert out.latest is not None and out.latest.id == new.id
    assert out.latest.period_end == TODAY


# ---------------------------------------------------------------- start side
def test_start_recap_windows_end_today(db):
    _seed_day(db, TODAY, matches=2)
    week = hc_service.start_recap(db, "week", today=TODAY)
    assert week.period_start == WEEK_START and week.period_end == TODAY
    assert week.status == "generating"

    month = hc_service.start_recap(db, "month", today=TODAY)
    assert month.period_start == MONTH_START and month.period_end == TODAY
    # Week and month are independent rows.
    assert db.query(HeadCoachRecap).count() == 2


def test_start_recap_validation(db):
    # Unknown window type.
    try:
        hc_service.start_recap(db, "day", today=TODAY)
        raise AssertionError("expected ValueError for bad period_type")
    except ValueError:
        pass
    # Empty window: data exists, but only OUTSIDE the last 7 days.
    _seed_day(db, TODAY - dt.timedelta(days=10))
    try:
        hc_service.start_recap(db, "week", today=TODAY)
        raise AssertionError("expected ValueError for empty window")
    except ValueError:
        pass
    # ...that same data IS inside the last 30 days.
    out = hc_service.start_recap(db, "month", today=TODAY)
    assert out.status == "generating"
    # One at a time per window type.
    try:
        hc_service.start_recap(db, "month", today=TODAY)
        raise AssertionError("expected ValueError while generating")
    except ValueError:
        pass


def test_same_day_press_reuses_row(db, monkeypatch):
    monkeypatch.setattr(hc_service, "_call_recap_model", _fake_recap)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")
    _seed_day(db, TODAY)
    first = hc_service.start_recap(db, "week", today=TODAY)
    hc_service.run_recap_job(first.id, db)

    second = hc_service.start_recap(db, "week", today=TODAY)
    assert second.id == first.id and second.status == "generating"
    assert db.query(HeadCoachRecap).count() == 1
    hc_service.run_recap_job(second.id, db)
    assert _latest(db).status == "done"


# ------------------------------------------------------------------ the job
def test_run_recap_job_fills_row_and_stats(db, monkeypatch):
    monkeypatch.setattr(hc_service, "_call_recap_model", _fake_recap)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")
    _seed_day(db, TODAY, minutes=90, matches=3)  # 2W/1L, inside the window
    _seed_day(db, WEEK_START - dt.timedelta(days=1), minutes=999)  # just outside

    # New-opponent counting: Anna first met in the PREVIOUS window and met
    # again now (not new); Binh first met inside the current window (new).
    anna = Player(name="Anna", points=950)
    binh = Player(name="Binh", points=950)
    db.add_all([anna, binh])
    db.commit()
    official = category_id(db, "official_match")

    def _vs(day: dt.date, opponent_id: int) -> Match:
        return Match(
            date=day, category_id=official, my_sets=3, opp_sets=1,
            opponent_id=opponent_id,
        )

    db.add_all([
        _vs(WEEK_START - dt.timedelta(days=1), anna.id),  # previous window
        _vs(TODAY, anna.id),
        _vs(TODAY, binh.id),
    ])
    db.commit()

    out = hc_service.start_recap(db, "week", today=TODAY)
    hc_service.run_recap_job(out.id, db)

    rec = _latest(db)
    assert rec.status == "done" and rec.error_msg is None
    assert rec.headline == "Giai đoạn ổn."
    assert rec.went_well == ["Đánh 2 trận"] and rec.focus_next == ["Thêm 1 buổi thể lực"]
    cur = rec.stats.current
    assert cur.minutes_total == 90  # the 999m day is outside the 7-day window
    # 3 unnamed (2W/1L) + the 2 named wins vs Anna and Binh.
    assert cur.matches_played == 5 and cur.matches_wins == 4 and cur.matches_losses == 1
    # Binh is new (first-ever meeting in the window); Anna was met the window
    # before — where SHE was the new one.
    assert cur.new_opponents == 1
    # The just-outside day falls in the PREVIOUS 7-day window.
    assert rec.stats.previous is not None
    assert rec.stats.previous.minutes_total == 999
    assert rec.stats.previous.new_opponents == 1


def test_run_recap_job_no_previous_before_first_data(db, monkeypatch):
    monkeypatch.setattr(hc_service, "_call_recap_model", _fake_recap)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")
    _seed_day(db, TODAY, minutes=60)  # the only data ever

    out = hc_service.start_recap(db, "week", today=TODAY)
    hc_service.run_recap_job(out.id, db)
    rec = _latest(db)
    assert rec.status == "done" and rec.stats.previous is None


def test_run_recap_job_error_marks_row(db, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(hc_service, "_call_recap_model", _boom)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")
    _seed_day(db, TODAY)

    out = hc_service.start_recap(db, "week", today=TODAY)
    hc_service.run_recap_job(out.id, db)

    rec = _latest(db)
    assert rec.status == "error" and "ollama down" in rec.error_msg


# ------------------------------------------------------------ crash recovery
def test_recover_stuck_recap(db):
    db.add(
        HeadCoachRecap(
            period_type="week",
            period_start=WEEK_START,
            period_end=TODAY,
            status="generating",
        )
    )
    db.commit()
    hc_service.recover_stuck_jobs(db)
    row = db.query(HeadCoachRecap).first()
    assert row.status == "error" and row.error_msg


# ------------------------------------------------------------------- the API
def test_recaps_api_shape(db, client, monkeypatch):
    monkeypatch.setattr(hc_service, "run_recap_job", lambda *a, **k: None)
    real_today = dt.date.today()
    _seed_day(db, real_today, matches=1)

    # GET is read-only: nothing generated yet.
    resp = client.get("/api/head-coach/recaps?period=week")
    assert resp.status_code == 200 and resp.json()["latest"] is None
    assert client.get("/api/head-coach/recaps?period=year").status_code == 400

    # The button starts a generation of the window ending today.
    resp = client.post(
        "/api/head-coach/recaps/generate", json={"period_type": "week"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "generating"
    assert body["period_end"] == real_today.isoformat()
    assert body["period_start"] == (real_today - dt.timedelta(days=6)).isoformat()

    # Now GET surfaces it; a second press while generating is refused.
    resp = client.get("/api/head-coach/recaps?period=week")
    assert resp.json()["latest"]["id"] == body["id"]
    resp = client.post(
        "/api/head-coach/recaps/generate", json={"period_type": "week"}
    )
    assert resp.status_code == 400

    # Unknown window type → 400.
    resp = client.post(
        "/api/head-coach/recaps/generate", json={"period_type": "quarter"}
    )
    assert resp.status_code == 400
