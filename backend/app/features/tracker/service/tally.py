"""W/L/T letters and the match-stats accumulators.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.features.tracker import schemas
from app.features.tracker.models import (
    Match,
)


def _result_letter(my_sets: int, opp_sets: int) -> str:
    if my_sets > opp_sets:
        return "W"
    if my_sets < opp_sets:
        return "L"
    return "T"


def _result_of(m: Match) -> str:
    return _result_letter(m.my_sets, m.opp_sets)


def _blank_match_stats() -> dict:
    return {"total": 0, "wins": 0, "losses": 0, "ties": 0, "sets_won": 0, "sets_lost": 0}


def win_rate(wins: int, losses: int) -> float | None:
    """Win rate over *decided* matches (ties excluded). None if none decided."""
    decided = wins + losses
    return (wins / decided) if decided else None


def _tally(s: dict, m: Match) -> None:
    """Fold one playing match into a _blank_match_stats() accumulator."""
    s["total"] += 1
    s["sets_won"] += m.my_sets
    s["sets_lost"] += m.opp_sets
    r = _result_of(m)
    if r == "W":
        s["wins"] += 1
    elif r == "L":
        s["losses"] += 1
    else:
        s["ties"] += 1


def _finalize_match_stats(s: dict) -> schemas.MatchStats:
    return schemas.MatchStats(**s, win_rate=win_rate(s["wins"], s["losses"]))


def _is_vs_pips(m: Match) -> bool:
    """Either listed opponent plays pimpled rubber (covers doubles).

    The SAME predicate backs build_stats' vs_pips bucket (coach bundle
    numbers) and the Profile tab's vs_pips KPI, so the two can never
    disagree. (Was the multi-bucket _in_stats_bucket until the Daily Tracker
    win-rate cards + their drill-down endpoint were removed 2026-08-02.)"""
    if m.is_nonplaying:
        return False
    return bool(
        (m.opponent and m.opponent.plays_pips)
        or (m.opponent2 and m.opponent2.plays_pips)
    )


# SQL ordering for "newest first" — order_index then id break same-day ties.
_NEWEST_FIRST = (Match.date.desc(), Match.order_index.desc(), Match.id.desc())


def _playing_matches(db: Session):
    """Base query for playing matches (nonplaying rows excluded), eager-
    loading the full line-up + event so names resolve without N+1."""
    return (
        db.query(Match)
        .filter(Match.is_nonplaying == False)  # noqa: E712
        .options(
            selectinload(Match.event),
            selectinload(Match.opponent),
            selectinload(Match.opponent2),
            selectinload(Match.partner),
        )
    )
