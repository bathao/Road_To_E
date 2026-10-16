"""ELO breakdowns: per-bucket trend and per-opponent net.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.features.tracker import rating, schemas
from app.features.tracker.models import (
    Match,
)

from .periods import _bucket_ranges
from .tally import _playing_matches


def build_rating_breakdown(
    db: Session,
    date_from: dt.date,
    date_to: dt.date,
    unit: str = "day",
    replay: rating.ReplayResult | None = None,
    with_movers: bool = True,
) -> schemas.MyRatingBreakdownOut:
    """Net ELO change per day/week/month bucket + every counted match's ±Δ.

    Replayed on demand via rating.replay — nothing stored. The rating is
    GLOBAL: no discipline/category filtering here (deltas could be filtered,
    but a filtered "rating at end of bucket" would be a lie — decided v1
    2026-07-27). `with_movers=False` skips building the per-match rows for
    callers that only read the buckets (the coach bundle)."""
    _final, steps = replay or rating.replay(db)
    anchor_date = rating.get_my_anchor_date(db)
    anchor_points = rating.get_my_points(db)

    def value_at(day: dt.date) -> int | None:
        """Replayed rating at the END of `day` (carry-forward over quiet
        days); None before the anchor, when no rating existed yet."""
        if day < anchor_date:
            return None
        val = float(anchor_points)
        for s in steps:
            if s.date > day:
                break
            val = s.rating_after
        return round(val)

    buckets: list[schemas.RatingBucketOut] = []
    for key, label, b_from, b_to in _bucket_ranges(date_from, date_to, unit):
        in_bucket = [s for s in steps if b_from <= s.date <= b_to]
        buckets.append(
            schemas.RatingBucketOut(
                key=key,
                label=label,
                date_from=b_from,
                date_to=b_to,
                delta=round(sum(s.delta for s in in_bucket), 1),
                # Matches only — placement bonuses move the delta, not this.
                counted=sum(1 for s in in_bucket if s.match_id is not None),
                rating_end=value_at(b_to),
            )
        )

    in_range = [s for s in steps if date_from <= s.date <= date_to]

    # EVERY counted match becomes a table row (the GUI sorts client-side).
    # One date-window query batch-loads them (a superset that includes
    # skipped matches — harmless, and it avoids an unbounded IN(id...) list).
    match_by_id: dict[int, Match] = (
        {
            m.id: m
            for m in _playing_matches(db).filter(
                Match.date >= date_from, Match.date <= date_to
            )
        }
        if with_movers and in_range
        else {}
    )

    def _mover(s: "rating.ReplayStep") -> schemas.RatingMoverOut:
        if s.match_id is None:  # tournament placement bonus, not a match
            return schemas.RatingMoverOut(
                match_id=None,
                date=s.date,
                delta=round(s.delta, 1),
                discipline=s.bonus_discipline or "singles",
                opponent_name=None,
                my_sets=0,
                opp_sets=0,
                bonus_label=s.bonus_label,
            )
        m = match_by_id.get(s.match_id)
        return schemas.RatingMoverOut(
            match_id=s.match_id,
            date=s.date,
            delta=round(s.delta, 1),
            discipline=m.discipline if m else "singles",
            opponent_name=m.opponent.name if m and m.opponent else None,
            opponent2_name=m.opponent2.name if m and m.opponent2 else None,
            partner_name=m.partner.name if m and m.partner else None,
            my_sets=m.my_sets if m else 0,
            opp_sets=m.opp_sets if m else 0,
        )

    # Newest first — the GUI table's default sort order.
    movers = [_mover(s) for s in reversed(in_range)] if with_movers else []

    # Rating carried INTO the range; the anchor itself counts as the start
    # when the range begins on/before the anchor day.
    rating_start = value_at(date_from - dt.timedelta(days=1))
    if rating_start is None and date_to >= anchor_date:
        rating_start = anchor_points

    # All-time peak on END-OF-DAY values (the last step of each day), so the
    # star lands on a real point of the by-day curve; the anchor day is a
    # candidate too. First day the peak was reached wins a tie.
    end_of_day: dict[dt.date, float] = {anchor_date: float(anchor_points)}
    for s in steps:
        end_of_day[s.date] = s.rating_after
    peak_date, peak_val = max(
        end_of_day.items(), key=lambda kv: (round(kv[1]), -kv[0].toordinal())
    )

    return schemas.MyRatingBreakdownOut(
        peak_rating=round(peak_val),
        peak_date=peak_date,
        date_from=date_from,
        date_to=date_to,
        unit=unit,
        anchor_date=anchor_date,
        anchor_points=anchor_points,
        total_delta=round(sum(s.delta for s in in_range), 1),
        counted=sum(1 for s in in_range if s.match_id is not None),
        rating_start=rating_start,
        rating_end=value_at(date_to),
        buckets=buckets,
        movers=movers,
    )


def elo_by_opponent(
    db: Session,
    date_from: dt.date,
    date_to: dt.date,
    replay: rating.ReplayResult | None = None,
) -> list[dict]:
    """Net counted-ELO change per NAMED opponent over the window — who the
    points are being lost to / won from (the Head Coach's strategy input).

    Each counted match's delta is attributed to EVERY named opponent in it
    (a doubles loss "costs" against both players — honest as "matches with X
    present"); placement bonuses have no opponent and are skipped. Returns
    [{name, matches, net}] sorted biggest net gain first."""
    _final, steps = replay or rating.replay(db)
    in_range = [
        s for s in steps
        if s.match_id is not None and date_from <= s.date <= date_to
    ]
    if not in_range:
        return []
    # Same batch-load trick as build_rating_breakdown's movers: one
    # date-window query instead of an unbounded IN(id...) list.
    match_by_id: dict[int, Match] = {
        m.id: m
        for m in _playing_matches(db).filter(
            Match.date >= date_from, Match.date <= date_to
        )
    }
    acc: dict[str, dict] = {}
    for s in in_range:
        m = match_by_id.get(s.match_id)
        if m is None:
            continue
        for opp in (m.opponent, m.opponent2):
            if opp is None:
                continue
            a = acc.setdefault(
                opp.name, {"name": opp.name, "matches": 0, "net": 0.0}
            )
            a["matches"] += 1
            a["net"] += s.delta
    out = sorted(acc.values(), key=lambda a: -a["net"])
    for a in out:
        a["net"] = round(a["net"], 1)
    return out
