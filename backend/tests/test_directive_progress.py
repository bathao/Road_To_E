"""Directive live progress: this week's database actual vs weekly targets."""
from __future__ import annotations

import datetime as dt
import json

from app.features.head_coach import service as hc_service
from app.features.head_coach.models import HeadCoachAssessment
from app.features.tracker.models import Activity, Match

from conftest import category_id

TODAY = dt.date.today()
WEEK_START = TODAY - dt.timedelta(days=TODAY.weekday())  # Monday


def _make_assessment(db, directives: list[dict]) -> HeadCoachAssessment:
    row = HeadCoachAssessment(
        status="done",
        overall_assessment="x",
        directives_json=json.dumps(directives, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    return row


def test_directive_progress_computes_week_actuals(db):
    coach = category_id(db, "train_with_coach")
    official = category_id(db, "official_match")
    # This week: 90 coach minutes + one 3-2 singles match (5 sets ≈ 25 racket
    # minutes on top of the training 90 → 115m ≈ 1.9h).
    db.add_all([
        Activity(date=TODAY, category_id=coach, duration_minutes=90),
        Match(date=TODAY, category_id=official, my_sets=3, opp_sets=2),
        # Last week's data must NOT count.
        Activity(
            date=WEEK_START - dt.timedelta(days=1),
            category_id=coach,
            duration_minutes=60,
        ),
    ])
    db.commit()
    _make_assessment(db, [
        {"area": "training", "order": "Tập với HLV nhiều hơn", "metric": "coach_hours_per_week", "value": 3},
        {"area": "matches", "order": "Đánh nhiều trận đơn hơn", "metric": "singles_matches_per_week", "value": 4},
        {"area": "playing_hours", "order": "Cầm vợt nhiều hơn", "metric": "racket_hours_per_week", "value": 8},
        {"area": "skill", "order": "Không đo được", "metric": "", "value": None},
    ])

    out = hc_service.directive_progress(db)
    assert out.week_start == WEEK_START
    by_metric = {p.metric: p for p in out.items}
    # The untrackable directive is skipped.
    assert len(out.items) == 3

    assert by_metric["coach_hours_per_week"].actual == 1.5
    assert by_metric["coach_hours_per_week"].pct == 50
    assert by_metric["singles_matches_per_week"].actual == 1
    assert by_metric["singles_matches_per_week"].pct == 25
    assert by_metric["racket_hours_per_week"].actual == 1.9  # (90 + 25) / 60
    assert by_metric["racket_hours_per_week"].unit_vi == "hours"


def test_directive_progress_empty_without_assessment(db):
    out = hc_service.directive_progress(db)
    assert out.items == [] and out.assessment_id is None
