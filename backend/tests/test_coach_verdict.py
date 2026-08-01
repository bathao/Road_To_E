"""Verdict generation job — the last head-coach job with no direct test.

Mirrors the recap/chat job tests: the LLM call is monkeypatched and the job
runs synchronously on the injected test session.
"""
from __future__ import annotations

from app.features.head_coach import service as hc_service
from app.features.head_coach.models import HeadCoachAssessment


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
