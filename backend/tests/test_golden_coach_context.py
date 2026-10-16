"""Golden (characterization) tests for the Head Coach's context text.

``_bundle_to_text`` (verdict + chat) and ``_recap_bundle_to_text`` (recaps)
turn the database into the Vietnamese fact block the model reads. Both are
slated to move into a shared section renderer (REFACTOR.md §4.2); these
tests pin the exact text produced for one fixed dataset so that refactor
can be checked line by line.

The gatherers read ``dt.date.today()`` in several places (stats windows, the
7-day plan scaffold, task streaks, the training report), so the clock is
frozen to 2026-08-01 by swapping ``datetime.date`` for a subclass whose
``today()`` is fixed. The ELO anchor default is 2026-07-27, so matches from
that day on would move the rating; the fixture anchors it on 2026-07-01
instead so the weekly ELO trend has several buckets.
"""
from __future__ import annotations

import datetime as dt
import types

import pytest

from conftest import assert_golden, category_id
from app.features.head_coach import service as hc_service
from app.features.head_coach.service import verdict as hc_verdict
from app.features.head_coach.service import recap as hc_recap
from app.features.head_coach.service import bundle as hc_bundle
from app.features.head_coach.service import directives as hc_directives
from app.features.head_coach.service import render as hc_render
from app.features.head_coach.models import CoachNote, HeadCoachRecap
from app.features.tournament import schemas as t_schemas
from app.features.tournament import service as t_service
from app.features.tracker import rating, schemas, service
from app.features.tracker.service import boards as tracker_boards
from app.features.tracker.service import grid as tracker_grid
from app.features.tracker.service import players as tracker_players
from app.features.tracker.models import Activity, DayNote, Player, SessionNote, Setting
from app.features.training import service as training_service

TODAY = dt.date(2026, 8, 1)  # a Saturday


class _FrozenDate(dt.date):
    @classmethod
    def today(cls):
        return cls(TODAY.year, TODAY.month, TODAY.day)


# Every app module that reads the clock does so as ``dt.date.today()``; each
# gets a copy of the datetime module whose ``date`` is the frozen subclass.
# (Patching ``datetime.date`` itself would break SQLAlchemy's own
# ``isinstance(value, datetime.date)`` check on real date objects.)
_CLOCK_MODULES = (
    hc_bundle,
    hc_directives,
    hc_recap,
    hc_render,
    tracker_grid,
    tracker_boards,
    tracker_players,
    training_service,
    t_service,
    rating,
)


@pytest.fixture()
def frozen_today(monkeypatch):
    shim = types.ModuleType("datetime")
    shim.__dict__.update(dt.__dict__)
    shim.date = _FrozenDate
    for mod in _CLOCK_MODULES:
        monkeypatch.setattr(mod, "dt", shim)
    yield TODAY


def _day(offset: int) -> dt.date:
    return TODAY + dt.timedelta(days=offset)


def _seed(client, db) -> None:
    coach_cat = category_id(db, "train_with_coach")
    partner_cat = category_id(db, "training_with_partner")
    serve_cat = category_id(db, "serve")
    practice = category_id(db, "practice_match")
    official = category_id(db, "official_match")
    tournament = category_id(db, "tournament_match")
    coaches = {c.name: c for c in service.list_coaches(db)}
    minh, phi = coaches["Minh Thới"], coaches["Phi Vũ"]

    anna = Player(name="Anna", points=950)
    binh = Player(name="Bình", points=1200, plays_pips=True)
    cuong = Player(name="Cường", points=700)
    buddy = Player(name="Đồng Đội", points=900)
    db.add_all([anna, binh, cuong, buddy])
    db.commit()

    db.add_all([
        Activity(date=_day(-4), category_id=coach_cat, duration_minutes=60,
                 coach_id=minh.id, is_package_start=True),
        Activity(date=_day(-2), category_id=coach_cat, duration_minutes=60,
                 coach_id=phi.id),
        Activity(date=_day(-3), category_id=partner_cat, duration_minutes=45),
        Activity(date=_day(-1), category_id=serve_cat, duration_minutes=20),
        # Previous week + previous month: feeds the recap comparisons.
        Activity(date=_day(-9), category_id=coach_cat, duration_minutes=60,
                 coach_id=minh.id),
        Activity(date=_day(-45), category_id=partner_cat, duration_minutes=90),
        DayNote(date=_day(-2), text="Chân phải hơi mỏi sau buổi tập."),
        DayNote(date=_day(-7), text="Ngủ ít, đánh thiếu tập trung."),
    ])
    db.commit()

    # Journal: the coach day -4 carries advice (one open, one done), a
    # drill and a recap; a lesson sits on a coach-less day.
    for kind, text, tags in [
        ("advice", "Giữ thấp trọng tâm khi giật phải", ["fh_topspin"]),
        ("advice", "Đã sửa: không nhấc gót khi đỡ giao", []),
        ("drill", "FH topspin vs block 3×10 phút", ["fh_topspin"]),
        ("recap", "Buổi tập tốt, chân nhanh hơn", []),
    ]:
        service.create_session_note(db, schemas.SessionNoteIn(
            date=_day(-4), kind=kind, tags=tags, text=text,
        ))
    done = db.query(SessionNote).filter(SessionNote.text.startswith("Đã sửa")).one()
    done.is_done = True
    db.commit()
    service.create_session_note(db, schemas.SessionNoteIn(
        date=_day(-1), kind="lesson", text="Giao ngắn hiệu quả hơn giao dài với Anna",
    ))

    # Tracking board: a coach-given daily task with a 2-day streak ending
    # yesterday, a plain self task, and a finished one.
    daily = service.create_task(db, schemas.TaskIn(
        title="Nhảy dây 100 cái", source="coach", is_daily=True,
    )).tasks[-1]
    for off in (-2, -1):
        service.set_task_check(db, daily.id, schemas.TaskCheckIn(date=_day(off), checked=True))
    service.create_task(db, schemas.TaskIn(
        title="Đọc sách chiến thuật", note="chương 3", source="self",
    ))
    finished = service.create_task(db, schemas.TaskIn(title="Mua vợt mới", source="ai")).tasks[-1]
    service.update_task(db, finished.id, schemas.TaskUpdate(status="done"))
    service.create_memo(db, schemas.MemoIn(text="Giữ bình tĩnh khi bị dẫn điểm"))
    service.create_memo(db, schemas.MemoIn(text="Giao bóng đa dạng ngay từ set 1"))
    hc_service.add_note(db, "Mục tiêu: hạng E trước 2027.")
    # created_at is a wall-clock timestamp (not the frozen date) and shows
    # in the text — pin it.
    db.query(CoachNote).one().created_at = dt.datetime(2026, 7, 20, 9, 0)
    # Anchor the rating a month back so the weekly ELO path has several
    # buckets (the default anchor, 2026-07-27, would leave exactly one).
    db.add(Setting(key="my_points_date", value="2026-07-01"))
    db.commit()

    # Upcoming tournaments: a 2-day knockout with two entries, a league.
    t_service.create_tournament(db, t_schemas.TournamentIn(
        name="SG Cup", location="Quận 1", level_limit="E F G",
        start_date=_day(2), end_date=_day(3),
        entries=[
            t_schemas.EntryIn(discipline="singles"),
            t_schemas.EntryIn(discipline="doubles", partner_id=buddy.id),
        ],
    ))
    t_service.create_tournament(db, t_schemas.TournamentIn(
        name="League tháng 8", start_date=_day(4), format="league",
        points_limit=1300, note="5 trận vòng tròn",
        entries=[t_schemas.EntryIn(discipline="singles")],
    ))

    # Training Center: two completed sessions, mild pain on the second
    # (intensity bias drops to -1).
    s1 = training_service._materialise(db, "foundation", 1)
    for it in sorted(s1.items, key=lambda it: it.sort_order)[:2]:
        training_service.tick_item(db, s1.id, it.id, True)
    training_service.complete_session(db, "foundation", 1, None, done_on=_day(-2))
    s2 = training_service._materialise(db, "foundation", 2)
    for it in s2.items:
        training_service.tick_item(db, s2.id, it.id, True)
    training_service.complete_session(db, "foundation", 2, None, pain="mild", done_on=TODAY)

    matches = [
        # Before the anchor: counts in the stats, never in the ELO.
        {"date": _day(-42).isoformat(), "category_id": practice,
         "my_sets": 3, "opp_sets": 1, "opponent_id": cuong.id},
        {"date": _day(-17).isoformat(), "category_id": practice,
         "my_sets": 0, "opp_sets": 3},  # unnamed opponent (no ELO: nobody named)
        {"date": _day(-12).isoformat(), "category_id": official,
         "my_sets": 3, "opp_sets": 1, "opponent_id": anna.id},
        # From the anchor (2026-07-27) on.
        {"date": _day(-5).isoformat(), "category_id": practice,
         "my_sets": 1, "opp_sets": 3, "opponent_id": binh.id,
         "handicap": -1, "handicap_pattern": "2-0-2"},
        {"date": _day(-3).isoformat(), "category_id": official,
         "my_sets": 3, "opp_sets": 2, "opponent_id": anna.id},
        {"date": _day(-2).isoformat(), "category_id": official, "discipline": "doubles",
         "my_sets": 3, "opp_sets": 1, "partner_id": buddy.id,
         "opponent_id": anna.id, "opponent2_id": cuong.id},
        {"date": _day(-1).isoformat(), "category_id": official,
         "my_sets": 2, "opp_sets": 3, "opponent_id": anna.id},
        {"date": TODAY.isoformat(), "category_id": tournament,
         "my_sets": 3, "opp_sets": 0, "opponent_id": cuong.id, "handicap": 2},
    ]
    for payload in matches:
        r = client.post("/api/tracker/matches", json=payload)
        assert r.status_code == 200, r.text


def _verdict_payload(*_a, **_k) -> dict:
    return {
        "overall_assessment": "Khối lượng tuần này quá thấp.",
        "top_priorities": [],
        "directives": [],
        "week_plan": [],
        "watch_items": [],
    }


def _recap_payload(*_a, **_k) -> dict:
    return {"headline": "Ổn.", "overall": "Giữ nhịp.", "went_well": [],
            "concerns": [], "focus_next": []}


def test_verdict_context_golden(frozen_today, client, db, monkeypatch):
    _seed(client, db)
    seen: dict[str, str] = {}

    def capture(context_text: str, player_name: str, model: str) -> dict:
        seen["text"] = context_text
        seen["player"] = player_name
        return _verdict_payload()

    monkeypatch.setattr(hc_verdict, "_call_model", capture)
    monkeypatch.setattr(hc_verdict, "resolve_model", lambda: "test-model")
    out = hc_service.start_generate(db)
    hc_service.run_generate_job(out.id, db)
    assert hc_service.get_latest(db).status == "done"
    assert seen["player"] == "the player"  # no va_profile row in the test DB
    assert_golden("verdict_context_2026-08-01.txt", seen["text"])


@pytest.mark.parametrize("period_type", ["week", "month"])
def test_recap_context_golden(frozen_today, client, db, monkeypatch, period_type):
    _seed(client, db)
    seen: dict[str, str] = {}

    def capture(context_text: str, player_name: str, period_type: str, model: str) -> dict:
        seen["text"] = context_text
        return _recap_payload()

    monkeypatch.setattr(hc_recap, "_call_recap_model", capture)
    monkeypatch.setattr(hc_recap, "resolve_model", lambda: "test-model")
    out = hc_service.start_recap(db, period_type, today=TODAY)
    hc_service.run_recap_job(out.id, db)
    row = db.get(HeadCoachRecap, out.id)
    assert row.status == "done", row.error_msg
    assert_golden(f"recap_{period_type}_context_2026-08-01.txt", seen["text"])
