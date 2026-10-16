"""Live progress of the verdict's weekly directives against the database.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.features.head_coach import schemas
from app.features.tracker import service as tracker_service
from app.features.training.models import TrainingSession

from .verdict import get_latest

_METRIC_UNIT_VI = {
    "physical_sessions_per_week": "sessions",
    "racket_hours_per_week": "hours",
    "coach_hours_per_week": "hours",
    "matches_per_week": "matches",
    "singles_matches_per_week": "matches",
    "doubles_matches_per_week": "matches",
    "matches_vs_pips_per_week": "matches",
}


def _week_actual(db: Session, metric: str, week_start: dt.date, today: dt.date) -> float:
    """This week's (Mon → today) actual for one directive metric, computed
    from the database — never self-reported."""
    if metric == "physical_sessions_per_week":
        return float(
            db.query(TrainingSession)
            .filter(
                TrainingSession.status == "done",
                TrainingSession.done_on >= week_start,
                TrainingSession.done_on <= today,
            )
            .count()
        )
    stats = tracker_service.build_stats(db, week_start, today)
    if metric == "racket_hours_per_week":
        return round(stats.racket_minutes_total / 60, 1)
    if metric == "coach_hours_per_week":
        coach = next(
            (c for c in stats.minutes_by_category if c.key == "train_with_coach"), None
        )
        return round((coach.minutes if coach else 0) / 60, 1)
    if metric == "matches_per_week":
        return float(stats.overall.total)
    if metric == "singles_matches_per_week":
        return float(stats.singles.total)
    if metric == "doubles_matches_per_week":
        return float(stats.doubles.total)
    if metric == "matches_vs_pips_per_week":
        return float(stats.vs_pips.total)
    return 0.0


def directive_progress(db: Session) -> schemas.DirectiveProgressOut:
    """Live progress of the latest verdict's machine-trackable directives:
    this week's database actual vs the weekly target."""
    latest = get_latest(db)
    if latest.empty or latest.id is None:
        return schemas.DirectiveProgressOut()
    today = dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())  # Monday

    items: list[schemas.DirectiveProgress] = []
    for i, d in enumerate(latest.directives):
        if not d.metric or d.metric not in _METRIC_UNIT_VI or not d.value:
            continue
        actual = _week_actual(db, d.metric, week_start, today)
        pct = max(0, min(100, round(100 * actual / d.value)))
        items.append(
            schemas.DirectiveProgress(
                index=i,
                area=d.area,
                order=d.order,
                metric=d.metric,
                value=d.value,
                actual=actual,
                pct=pct,
                unit_vi=_METRIC_UNIT_VI[d.metric],
            )
        )
    return schemas.DirectiveProgressOut(
        assessment_id=latest.id, week_start=week_start, items=items
    )
