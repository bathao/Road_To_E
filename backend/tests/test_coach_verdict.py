"""Verdict generation job — the last head-coach job with no direct test.

Mirrors the recap/chat job tests: the LLM call is monkeypatched and the job
runs synchronously on the injected test session.
"""
from __future__ import annotations

import datetime as dt

from conftest import category_id
from app.features.head_coach import service as hc_service
from app.features.head_coach.models import HeadCoachAssessment
from app.features.tracker.models import Match, Player


def _fake_verdict(*_args, **_kwargs) -> dict:
    return {
        "overall_assessment": "Khối lượng tuần này quá thấp.",
        "top_priorities": [{"title": "Tăng số trận đơn", "why": "ít trận", "source": "match"}],
        "directives": [
            {"area": "matches", "order": "Đánh 5 trận đơn mỗi tuần",
             "metric": "singles_matches_per_week", "value": 5},
            # Implausible value → the metric tag must be sanitized away.
            {"area": "training", "order": "Tập với HLV",
             "metric": "coach_hours_per_week", "value": 240},
        ],
        "week_plan": [{"day": "Thứ 2", "focus": "Thể lực"}],
        "watch_items": ["Dữ liệu còn mỏng"],
    }


def test_run_generate_job_fills_snapshot(db, monkeypatch):
    monkeypatch.setattr(hc_service, "_call_model", _fake_verdict)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")

    out = hc_service.start_generate(db)
    hc_service.run_generate_job(out.id, db)

    latest = hc_service.get_latest(db)
    assert latest.id == out.id and latest.status == "done"
    assert latest.overall_assessment == "Khối lượng tuần này quá thấp."
    assert latest.top_priorities[0].title == "Tăng số trận đơn"
    assert latest.week_plan[0].day == "Thứ 2"
    assert latest.watch_items == ["Dữ liệu còn mỏng"]
    # Sanitizer: plausible metric kept, implausible one stripped to text-only.
    assert latest.directives[0].metric == "singles_matches_per_week"
    assert latest.directives[1].metric == "" and latest.directives[1].value is None
    # The frozen bundle rides along for the sources view.
    assert latest.sources.generated_for_range


def test_verdict_bundle_h2h_progression_and_elo_by_opponent(db):
    """Repeated-opponent progression + per-opponent ELO (user 2026-08-04):
    the verdict bundle's h2h lines carry the recent match sequence (oldest →
    newest, with each match's handicap — a per-set pattern renders verbatim)
    and the context names who the window's ELO went to."""
    today = dt.date.today()
    d_old, d_new = today - dt.timedelta(days=3), today - dt.timedelta(days=1)
    anna = Player(name="Anna", points=950)
    db.add(anna)
    db.commit()
    official = category_id(db, "official_match")
    # Same opponent, same received pattern: 0-3 then 2-3 — closer while
    # still losing = the progression the prompt must credit.
    db.add_all([
        Match(date=d_old, category_id=official, my_sets=0, opp_sets=3,
              opponent_id=anna.id, handicap=-1, handicap_pattern="2-0-2"),
        Match(date=d_new, category_id=official, my_sets=2, opp_sets=3,
              opponent_id=anna.id, handicap=-1, handicap_pattern="2-0-2"),
    ])
    db.commit()

    bundle = hc_service.gather_bundle(db)

    def dm(d: dt.date) -> str:
        return f"{d.day:02d}/{d.month:02d}"

    h2h = bundle.match_detail["top_h2h"][0]
    assert h2h["name"] == "Anna"
    assert h2h["recent"] == (
        f"{dm(d_old)} L 0-3 (được chấp 2-0-2) → "
        f"{dm(d_new)} L 2-3 (được chấp 2-0-2)"
    )
    eo = bundle.match_detail["elo_by_opponent"]
    assert eo["gains"] == []  # two losses: Anna only drains
    assert eo["drains"][0]["name"] == "Anna"
    assert eo["drains"][0]["matches"] == 2 and eo["drains"][0]["net"] < 0

    text = hc_service._bundle_to_text(bundle)
    assert "diễn biến (cũ → mới)" in text
    assert "ELO THEO ĐỐI THỦ" in text and "mất điểm nhiều nhất vì" in text


def test_bundle_week_ahead_scaffold(db):
    """Week plan = the NEXT 7 DAYS, not a Mon–Sun calendar week (user
    2026-08-04): the context carries one pre-labelled line per day ("Thứ 6
    15/08") with any registered tournament mapped onto its real days — code
    does the calendar math, the model only copies labels."""
    from app.features.tournament import schemas as t_schemas
    from app.features.tournament import service as t_service

    today = dt.date.today()
    t_service.create_tournament(db, t_schemas.TournamentIn(
        name="SG Cup",
        start_date=today + dt.timedelta(days=2),
        end_date=today + dt.timedelta(days=3),
        entries=[t_schemas.EntryIn(discipline="singles")],
    ))

    text = hc_service._bundle_to_text(hc_service.gather_bundle(db))
    assert "=== 7 NGÀY TỚI" in text
    lbl = hc_service._day_label_vi
    assert f"- {lbl(today)} (HÔM NAY): (không có giải)" in text
    assert f"- {lbl(today + dt.timedelta(days=2))}: giải SG Cup — ngày 1/2" in text
    assert f"- {lbl(today + dt.timedelta(days=3))}: giải SG Cup — ngày 2/2" in text
    # Exactly 7 day lines, today first (index 1 = between the header's
    # closing "===" and the next section's opening "===").
    section = text.split("=== 7 NGÀY TỚI", 1)[1].split("===", 2)[1]
    assert section.count("\n  - ") == 7


def test_run_generate_job_error_marks_row(db, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(hc_service, "_call_model", _boom)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")

    out = hc_service.start_generate(db)
    hc_service.run_generate_job(out.id, db)

    row = db.get(HeadCoachAssessment, out.id)
    assert row.status == "error" and "ollama down" in row.error_msg
    # An error row never becomes "the latest verdict".
    assert hc_service.get_latest(db).empty is True
