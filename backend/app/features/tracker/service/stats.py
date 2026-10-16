"""Volume stats and period breakdowns for the Analysis panel.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.features.tracker import schemas

from .grid import _load_range, _physical_dates, racket_minutes_by_day
from .periods import _bucket_ranges, _date_range
from .tally import (
    _blank_match_stats,
    _finalize_match_stats,
    _is_vs_pips,
    _result_of,
    _tally,
    win_rate,
)


def build_stats(db: Session, date_from: dt.date, date_to: dt.date) -> schemas.StatsResponse:
    dates = _date_range(date_from, date_to)
    iso_dates = [d.isoformat() for d in dates]

    # with_match_relations=True so opponent.plays_pips is available for the
    # "vs đối thủ đánh gai" split (the opponent records are eager-loaded).
    rng = _load_range(db, date_from, date_to, with_match_relations=True)
    duration_cats = [c for c in rng.categories if c.type == "duration"]
    duration_ids = {c.id for c in duration_cats}
    activities = rng.activities
    matches = rng.matches

    # Per-day aggregates.
    minutes_per_day: dict[str, int] = {iso: 0 for iso in iso_dates}
    physical_per_day: dict[str, int] = {iso: 0 for iso in iso_dates}
    matches_per_day: dict[str, int] = {iso: 0 for iso in iso_dates}

    minutes_by_cat: dict[int, int] = {cid: 0 for cid in duration_ids}
    for a in activities:
        if a.category_id not in duration_ids or (a.duration_minutes or 0) <= 0:
            continue
        iso = a.date.isoformat()
        minutes_per_day[iso] = minutes_per_day.get(iso, 0) + a.duration_minutes
        minutes_by_cat[a.category_id] += a.duration_minutes

    for iso, keys in rng.checks_by_date.items():
        physical_per_day[iso] = physical_per_day.get(iso, 0) + len(keys)
    # Training Center sessions (from the cutover forward) also count as physical
    # days — mark the date present so days_physical / "trained" pick it up.
    for iso in rng.tc_physical:
        physical_per_day[iso] = physical_per_day.get(iso, 0) + 1

    # Match stats (playing matches only), split by discipline.
    overall = _blank_match_stats()
    singles = _blank_match_stats()
    doubles = _blank_match_stats()
    one_v_two = _blank_match_stats()  # me alone vs two opponents
    two_v_one = _blank_match_stats()  # me + partner vs one opponent
    vs_pips = _blank_match_stats()  # matches against a pimpled-rubber opponent

    by_discipline = {
        "doubles": doubles,
        "one_v_two": one_v_two,
        "two_v_one": two_v_one,
    }
    for m in matches:
        if m.is_nonplaying:
            continue
        iso = m.date.isoformat()
        matches_per_day[iso] = matches_per_day.get(iso, 0) + 1

        bucket = by_discipline.get(m.discipline, singles)
        _tally(overall, m)
        _tally(bucket, m)
        if _is_vs_pips(m):
            _tally(vs_pips, m)

    # Day-level counts.
    days_trained = sum(
        1
        for iso in iso_dates
        if minutes_per_day[iso] > 0
        or physical_per_day[iso] > 0
        or matches_per_day[iso] > 0
    )
    days_physical = sum(1 for iso in iso_dates if physical_per_day[iso] > 0)

    # In category display order (duration_cats already sorted by sort_order).
    minutes_by_category = [
        schemas.CategoryMinutes(
            key=c.key, label=c.label, minutes=minutes_by_cat.get(c.id, 0)
        )
        for c in duration_cats
    ]

    # Racket time over the range (training with racket + match play from sets).
    r_training, r_playing = racket_minutes_by_day(rng.categories, activities, matches)
    racket_training = sum(r_training.values())
    racket_matches = sum(r_playing.values())

    return schemas.StatsResponse(
        date_from=date_from,
        date_to=date_to,
        num_days=len(dates),
        days_trained=days_trained,
        days_physical=days_physical,
        minutes_total=sum(minutes_per_day.values()),
        minutes_by_category=minutes_by_category,
        racket_minutes_total=racket_training + racket_matches,
        racket_minutes_training=racket_training,
        racket_minutes_matches=racket_matches,
        overall=_finalize_match_stats(overall),
        singles=_finalize_match_stats(singles),
        doubles=_finalize_match_stats(doubles),
        one_v_two=_finalize_match_stats(one_v_two),
        two_v_one=_finalize_match_stats(two_v_one),
        vs_pips=_finalize_match_stats(vs_pips),
    )


def build_breakdown(
    db: Session, date_from: dt.date, date_to: dt.date, unit: str
) -> schemas.BreakdownResponse:
    """Per-sub-period metrics for the comparison bar chart."""
    rng = _load_range(db, date_from, date_to, with_match_relations=False)
    activities = rng.activities
    matches = rng.matches
    duration_ids = {c.id for c in rng.categories if c.type == "duration"}

    # Per-day aggregates.
    minutes: dict[str, int] = {}
    physical: set[str] = _physical_dates(rng)
    mcount: dict[str, int] = {}
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}

    for a in activities:
        if a.category_id in duration_ids and (a.duration_minutes or 0) > 0:
            iso = a.date.isoformat()
            minutes[iso] = minutes.get(iso, 0) + a.duration_minutes
    for m in matches:
        if m.is_nonplaying:
            continue
        iso = m.date.isoformat()
        mcount[iso] = mcount.get(iso, 0) + 1
        r = _result_of(m)
        if r == "W":
            wins[iso] = wins.get(iso, 0) + 1
        elif r == "L":
            losses[iso] = losses.get(iso, 0) + 1

    buckets: list[schemas.BreakdownBucket] = []
    for key, label, b_from, b_to in _bucket_ranges(date_from, date_to, unit):
        b_min = b_w = b_l = b_m = b_trained = b_phys = 0
        for d in _date_range(b_from, b_to):
            iso = d.isoformat()
            mins = minutes.get(iso, 0)
            mc = mcount.get(iso, 0)
            ph = iso in physical
            b_min += mins
            b_m += mc
            b_w += wins.get(iso, 0)
            b_l += losses.get(iso, 0)
            if ph:
                b_phys += 1
            if mins > 0 or ph or mc > 0:
                b_trained += 1
        buckets.append(
            schemas.BreakdownBucket(
                key=key,
                label=label,
                date_from=b_from,
                date_to=b_to,
                minutes=b_min,
                days_trained=b_trained,
                days_physical=b_phys,
                matches=b_m,
                wins=b_w,
                losses=b_l,
                win_rate=win_rate(b_w, b_l),
            )
        )

    return schemas.BreakdownResponse(unit=unit, buckets=buckets)
