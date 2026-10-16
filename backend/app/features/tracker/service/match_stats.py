"""Named-opponent match analytics: level × handicap, head-to-head, trends.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt
from typing import NamedTuple

from sqlalchemy.orm import Session, selectinload

from app.features.tracker import rating, schemas
from app.features.tracker.constants import DISCIPLINES
from app.features.tracker.models import (
    Category,
    Match,
)

from .periods import _bucket_ranges, _date_range
from .players import _level_of, level_from_points
from .tally import (
    _blank_match_stats,
    _finalize_match_stats,
    _is_vs_pips,
    _playing_matches,
    _result_of,
    _tally,
    win_rate,
)

# Relative levels are DERIVED from points (vs my current dynamic rating);
# "unrated" = opponent has no points yet. Hand-picked labels are retired.
_LEVEL_ORDER = ["below", "equal", "above", "unrated"]


_CATEGORY_KEY = {
    "practice": "practice_match",
    "official": "official_match",
    "tournament": "tournament_match",
}


# Match tracking with opponents began June 2026; ignore anything before.
MATCH_STATS_FLOOR = dt.date(2026, 6, 1)


def _query_named_matches(
    db: Session,
    date_from: dt.date,
    date_to: dt.date,
    discipline: str,
    category: str,
) -> list[Match]:
    """Playing matches with a named opponent in the range, in play order
    (order_index breaks same-day ties so "last_result" is truly the last)."""
    q = _playing_matches(db).filter(
        Match.date >= date_from,
        Match.date <= date_to,
        Match.opponent_id.isnot(None),
    )
    if discipline in DISCIPLINES:
        q = q.filter(Match.discipline == discipline)
    if category in _CATEGORY_KEY:
        cat = db.query(Category).filter(Category.key == _CATEGORY_KEY[category]).first()
        q = q.filter(Match.category_id == (cat.id if cat else -1))
    return q.order_by(Match.date, Match.order_index).all()


def _opponent_ids_in(db: Session, date_from: dt.date | None, date_to: dt.date | None) -> set[int]:
    """Distinct named opponents (either slot) in playing matches within the
    bounds (None = unbounded). Deliberately unfiltered — meeting someone in
    doubles still counts as having met them."""
    ids: set[int] = set()
    for col in (Match.opponent_id, Match.opponent2_id):
        q = db.query(col).filter(Match.is_nonplaying == False, col.isnot(None))  # noqa: E712
        if date_from is not None:
            q = q.filter(Match.date >= date_from)
        if date_to is not None:
            q = q.filter(Match.date <= date_to)
        ids.update(row[0] for row in q.distinct())
    return ids


def count_new_opponents(db: Session, date_from: dt.date, date_to: dt.date) -> int:
    """How many opponents played SINGLES vs me in the window whom I had never
    faced before it (the user's sparring goal: singles vs people not yet in
    the history — team formats dropped from the stat, user rule 2026-08-02).
    The "before" check still spans the FULL history including team matches —
    someone first met in doubles is not new when later playing them in
    singles. No tab floor, no filters.

    KEEP IN SYNC with build_match_stats' is_new (the met_in_singles path in
    _h2h_accumulate) — the same rule implemented in-memory; the definition
    changed 3 times in 2 days, and a future change must touch both.
    test_match_stats cross-asserts the two."""
    seen_before = _opponent_ids_in(db, None, date_from - dt.timedelta(days=1))
    faced_singles: set[int] = set()
    rows = (
        db.query(Match.opponent_id)
        .filter(
            Match.is_nonplaying == False,  # noqa: E712
            Match.discipline == "singles",
            Match.opponent_id.isnot(None),
            Match.date >= date_from,
            Match.date <= date_to,
        )
        .distinct()
    )
    faced_singles.update(row[0] for row in rows)
    return len(faced_singles - seen_before)


def _record_tail(rec: dict) -> dict:
    """The stat fields OpponentRecord and DoublesRecord share."""
    return {
        "played": rec["total"],
        "wins": rec["wins"],
        "losses": rec["losses"],
        "ties": rec["ties"],
        "sets_won": rec["sets_won"],
        "sets_lost": rec["sets_lost"],
        "win_rate": win_rate(rec["wins"], rec["losses"]),
        "last_date": rec["last_date"],
        "last_result": rec["last_result"],
        "matches": list(reversed(rec.get("matches", []))),  # most recent first
    }


class _H2HAcc(NamedTuple):
    overall: dict
    vs_pips: dict  # subset of overall: an opponent (either slot) plays pips
    singles_h2h: dict[int, dict]
    doubles_h2h: dict[str, dict]
    opp_brief: dict[int, dict]


def _h2h_accumulate(matches: list[Match], my_now: int) -> _H2HAcc:
    """One pass over the matches → overall tally + head-to-head records
    (singles per opponent; team-style per discipline+partner+pair)."""
    overall = _blank_match_stats()
    vs_pips = _blank_match_stats()
    singles_h2h: dict[int, dict] = {}  # keyed by opponent_id
    # Team-style matchups (doubles / 1v2 / 2v1), keyed by
    # discipline + partner + opponent-pair. Slots a format doesn't use stay None.
    doubles_h2h: dict[str, dict] = {}
    opp_brief: dict[int, dict] = {}  # every opponent seen -> {name, level, played}

    for m in matches:
        _tally(overall, m)
        # Same predicate as build_stats' bucket (the coach's numbers), so
        # the Profile KPI and the coach can never drift apart.
        if _is_vs_pips(m):
            _tally(vs_pips, m)

        # Dropdown list: count every opponent appearance (opp1 + opp2).
        for opp in (m.opponent, m.opponent2):
            if opp is not None:
                b = opp_brief.get(opp.id)
                if b is None:
                    b = opp_brief[opp.id] = {
                        "id": opp.id,
                        "name": opp.name,
                        "level": level_from_points(opp.points, my_now),
                        "points": opp.points,
                        "played": 0,
                        "plays_pips": bool(opp.plays_pips),
                        # Did any in-range meeting happen in singles? (the
                        # "new opponents" stat only counts singles meetings)
                        "met_in_singles": False,
                    }
                b["met_in_singles"] = b["met_in_singles"] or m.discipline == "singles"
                b["played"] += 1

        if m.discipline != "singles":
            # A team-style matchup = (my partner, if any) vs (their unordered
            # opponent pair) — covers doubles, 1v2 (no partner) and 2v1 (one
            # opponent). Discipline is part of the key so a 2v1 vs A never
            # merges with a doubles vs A + unnamed.
            opps = sorted(
                [
                    (m.opponent_id, m.opponent.name if m.opponent else "?",
                     _level_of(m.opp_points_snap, m.opponent, my_now)),
                    (m.opponent2_id, m.opponent2.name if m.opponent2 else None,
                     _level_of(m.opp2_points_snap, m.opponent2, my_now)),
                ],
                key=lambda t: (t[1] is None, (t[1] or "").lower()),
            )
            key = f"{m.discipline}|{m.partner_id}|{opps[0][0]}-{opps[1][0]}"
            rec = doubles_h2h.get(key)
            if rec is None:
                rec = doubles_h2h[key] = {
                    **_blank_match_stats(),
                    "key": key,
                    "discipline": m.discipline,
                    "partner_id": m.partner_id,
                    "partner_name": m.partner.name if m.partner else None,
                    "partner_level": _level_of(
                        m.partner_points_snap, m.partner, my_now
                    ),
                    "opp1_id": opps[0][0],
                    "opp1_name": opps[0][1] or "?",
                    "opp1_level": opps[0][2] or "unrated",
                    "opp2_id": opps[1][0],
                    "opp2_name": opps[1][1],
                    "opp2_level": opps[1][2],
                    "last_date": None,
                    "last_result": None,
                }
        else:
            rec = singles_h2h.get(m.opponent_id)
            if rec is None:
                rec = singles_h2h[m.opponent_id] = {
                    **_blank_match_stats(),
                    "opponent_id": m.opponent_id,
                    "name": m.opponent.name if m.opponent else "?",
                    # Derived at-match-time relative level (snapshot points vs
                    # my current rating) — the h2h record's label.
                    "level": _level_of(m.opp_points_snap, m.opponent, my_now)
                    or "unrated",
                    "last_date": None,
                    "last_result": None,
                    "matches": [],
                }
        rec.setdefault("matches", [])
        _tally(rec, m)
        # matches are ordered by date, so the last seen is the most recent.
        rec["last_date"] = m.date
        rec["last_result"] = _result_of(m)
        rec["matches"].append(
            schemas.MatchLine(
                date=m.date,
                discipline=m.discipline,
                my_sets=m.my_sets,
                opp_sets=m.opp_sets,
                result=_result_of(m),
                handicap=m.handicap or 0,
                handicap_pattern=m.handicap_pattern,
                event_name=m.event.name if m.event else None,
                round=m.round,
            )
        )
    return _H2HAcc(overall, vs_pips, singles_h2h, doubles_h2h, opp_brief)


def _trend_buckets(
    matches: list[Match],
    date_from: dt.date,
    date_to: dt.date,
    unit: str,
) -> list[schemas.MatchTrendBucket]:
    """W/L counts per day/week/month bucket. (The rolling-"form" overlay was
    removed with its chart, 2026-08-01 / cleanup 2026-08-21 — git history has
    it if the chart ever returns.)"""
    by_iso: dict[str, list[Match]] = {}
    for m in matches:
        by_iso.setdefault(m.date.isoformat(), []).append(m)
    trend: list[schemas.MatchTrendBucket] = []
    for key, label, b_from, b_to in _bucket_ranges(date_from, date_to, unit):
        b_m = b_w = b_l = 0
        for d in _date_range(b_from, b_to):
            for m in by_iso.get(d.isoformat(), []):
                b_m += 1
                r = _result_of(m)
                if r == "W":
                    b_w += 1
                elif r == "L":
                    b_l += 1
        trend.append(
            schemas.MatchTrendBucket(
                key=key,
                label=label,
                date_from=b_from,
                date_to=b_to,
                matches=b_m,
                wins=b_w,
                losses=b_l,
                win_rate=win_rate(b_w, b_l),
            )
        )
    return trend


def build_match_stats(
    db: Session,
    date_from: dt.date,
    date_to: dt.date,
    discipline: str = "all",
    category: str = "all",
    unit: str = "month",
    replay: rating.ReplayResult | None = None,
    with_trend: bool = True,
    overall_only: bool = False,
) -> schemas.MatchStatsResponse:
    """Stats over *named-opponent* matches only (opponent_id set, playing).

    Unlike build_stats (which counts every match), this tab is opponent-centric,
    so matches without a recorded opponent are excluded. A match is attributed to
    its primary opponent_id (opponent #1 in doubles); use the Singles filter for
    clean 1-v-1 analysis.

    The Profile tab stopped rendering the trend (its chart was removed
    2026-08-01), so the HTTP route passes `with_trend=False`; only the coach
    bundle (which reads `.trend` in-process) still computes the buckets.
    """
    # Clamp to the floor — this tab only covers matches from June 2026 on.
    date_from = max(date_from, MATCH_STATS_FLOOR)
    matches = _query_named_matches(db, date_from, date_to, discipline, category)

    # Relative levels derive from POINTS vs my current dynamic rating (the
    # hand-picked label was retired 2026-07-27). Per-MATCH grouping honours
    # the at-match-time snapshot; per-PLAYER listings use current points.
    # `replay` lets a caller doing several ELO-dependent builds (the coach
    # bundle) replay once and share the result.
    my_now = round((replay or rating.replay(db))[0])

    acc = _h2h_accumulate(matches, my_now)

    # The coach bundle's per-KIND calls (practice/official/tournament, in the
    # verdict AND every chat message) read `.overall`/`.vs_pips` only — skip
    # the new-opponents full-history scan, the h2h/opponent list building and
    # the trend buckets for them (review find 2026-08-09). Same accumulator,
    # so the numbers can't drift from the full path.
    if overall_only:
        return schemas.MatchStatsResponse(
            date_from=date_from,
            date_to=date_to,
            discipline=discipline,
            category=category,
            unit=unit,
            overall=_finalize_match_stats(acc.overall),
            vs_pips=_finalize_match_stats(acc.vs_pips),
            opponents=[],
            singles_h2h=[],
            doubles_h2h=[],
        )

    # "New" = played SINGLES vs me in range AND never faced before the range
    # starts, in ANY match (full history, both opponent slots, ignoring the
    # filters) — first met in doubles means not new when first playing them
    # in singles, and team-only meetings don't count at all (user rule
    # 2026-08-02). The in-range side follows the tab's filters, like every
    # other number on the tab. KEEP IN SYNC with count_new_opponents (the
    # recap path — same rule in SQL); test_match_stats cross-asserts them.
    seen_before = _opponent_ids_in(db, None, date_from - dt.timedelta(days=1))
    for oid, brief in acc.opp_brief.items():
        met_in_singles = brief.pop("met_in_singles")
        brief["is_new"] = met_in_singles and oid not in seen_before

    singles_list = sorted(
        (
            schemas.OpponentRecord(
                opponent_id=r["opponent_id"],
                name=r["name"],
                level=r["level"],
                **_record_tail(r),
            )
            for r in acc.singles_h2h.values()
        ),
        key=lambda o: (-o.played, o.name.lower()),
    )
    doubles_list = sorted(
        (
            schemas.DoublesRecord(
                **{
                    k: r[k]
                    for k in (
                        "key", "discipline", "partner_id", "partner_name",
                        "partner_level", "opp1_id", "opp1_name", "opp1_level",
                        "opp2_id", "opp2_name", "opp2_level",
                    )
                },
                **_record_tail(r),
            )
            for r in acc.doubles_h2h.values()
        ),
        key=lambda r: (-r.played, r.opp1_name.lower()),
    )
    opponents = sorted(
        (schemas.OpponentBrief(**b) for b in acc.opp_brief.values()),
        key=lambda o: (-o.played, o.name.lower()),
    )

    return schemas.MatchStatsResponse(
        date_from=date_from,
        date_to=date_to,
        discipline=discipline,
        category=category,
        unit=unit,
        overall=_finalize_match_stats(acc.overall),
        vs_pips=_finalize_match_stats(acc.vs_pips),
        new_opponents=sum(1 for b in acc.opp_brief.values() if b["is_new"]),
        opponents=opponents,
        singles_h2h=singles_list,
        doubles_h2h=doubles_list,
        trend=_trend_buckets(matches, date_from, date_to, unit)
        if with_trend
        else [],
    )


def build_handicap_split(
    db: Session,
    date_from: dt.date,
    date_to: dt.date,
    replay: rating.ReplayResult | None = None,
) -> dict[str, dict[str, dict]]:
    """Win rates by opponent level × handicap direction, for the Head Coach.

    Handicap is signed (+N = I give N points per set, -N = I receive), so a
    handicapped match plays out differently from an even one: receiving points
    against a stronger opponent pre-balances the match, while giving points to
    a weaker one puts me at a disadvantage. Win rates must therefore not be
    pooled across the directions. Named-opponent playing matches only, clamped
    to the same floor as build_match_stats. Empty cells are omitted.
    """
    date_from = max(date_from, MATCH_STATS_FLOOR)
    matches = (
        db.query(Match)
        .options(selectinload(Match.opponent))
        .filter(
            Match.date >= date_from,
            Match.date <= date_to,
            Match.is_nonplaying == False,  # noqa: E712
            Match.opponent_id.isnot(None),
        )
        .all()
    )
    my_now = round((replay or rating.replay(db))[0])
    acc: dict[str, dict[str, dict]] = {
        lv: {d: _blank_match_stats() for d in ("even", "receive", "give")}
        for lv in _LEVEL_ORDER
    }
    for m in matches:
        lv = _level_of(m.opp_points_snap, m.opponent, my_now) or "unrated"
        if lv not in acc:
            continue
        h = m.handicap or 0
        direction = "even" if h == 0 else ("give" if h > 0 else "receive")
        _tally(acc[lv][direction], m)
    return {
        lv: {
            d: {
                "played": s["total"],
                "wins": s["wins"],
                "losses": s["losses"],
                "win_rate": win_rate(s["wins"], s["losses"]),
            }
            for d, s in dirs.items()
            if s["total"]
        }
        for lv, dirs in acc.items()
    }
