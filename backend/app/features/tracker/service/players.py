"""The player pool: picker list, create/update, derived relative level.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.features.tracker import schemas
from app.features.tracker.models import (
    Match,
    Player,
)

from .text import _fold


def player_to_out(p: Player) -> schemas.PlayerOut:
    return schemas.PlayerOut(
        id=p.id,
        name=p.name,
        level=p.level,
        note=p.note,
        plays_pips=bool(p.plays_pips),
        points=p.points,
    )


# "Regulars" window for the picker ranking: how far back a training partner
# still counts as current (they rotate as the user changes clubs/groups).
_PICKER_RECENT_DAYS = 90


def list_players(
    db: Session, q: str = "", today: dt.date | None = None
) -> list[schemas.PlayerOut]:
    """Player search behind the match-editor pickers (user rules 2026-08-09).

    Matching is diacritic-insensitive and token-AND in any order ("go tuan"
    finds "Tuấn gỗ") — done in Python, the pool is ~100 rows. Ranking: names
    whose words START with every typed token first, then substring matches;
    within a tier the people I play MOST come first (appearances in MY
    matches in the last 90 days, then all-time — opponent AND partner slots
    both count: likely rematches and likely repeat partners alike). An empty
    query returns the current regulars on top — pick without typing."""
    today = today or dt.date.today()
    recent_floor = today - dt.timedelta(days=_PICKER_RECENT_DAYS)
    recent: dict[int, int] = {}
    total: dict[int, int] = {}
    rows = (
        db.query(Match.date, Match.opponent_id, Match.opponent2_id, Match.partner_id)
        .filter(Match.is_nonplaying == False)  # noqa: E712
        .all()
    )
    for date, *slots in rows:
        for pid in slots:
            if pid is None:
                continue
            total[pid] = total.get(pid, 0) + 1
            if date >= recent_floor:
                recent[pid] = recent.get(pid, 0) + 1

    tokens = _fold(q).split()

    def _rank(p: Player) -> tuple[int, int, int, str] | None:
        """None = no match; else the sort key (lower sorts first)."""
        folded = _fold(p.name)
        if any(t not in folded for t in tokens):
            return None
        words = folded.split()
        prefix = all(any(w.startswith(t) for w in words) for t in tokens)
        return (0 if prefix else 1, -recent.get(p.id, 0), -total.get(p.id, 0), folded)

    ranked = [
        (key, p) for p in db.query(Player).all() if (key := _rank(p)) is not None
    ]
    ranked.sort(key=lambda kp: kp[0])
    return [player_to_out(p) for _, p in ranked[:50]]


# Rank bands (H=0, then G..A per 200 points) — mirrors frontend shared/rank.ts.
_RANK_TOPS = (1000, 1200, 1400, 1600, 1800, 2000)


def _rank_band(points: int) -> int:
    if points < 800:
        return 0  # H
    for band, top in enumerate(_RANK_TOPS, start=1):
        if points <= top:
            return band  # G..B
    return 7  # A


def level_from_points(points: int | None, my_points: int) -> str:
    """Relative level derived from POINTS (retired the hand-picked label,
    2026-07-27): same rank band as my current dynamic rating = equal;
    no points yet = its own "unrated" bucket."""
    if points is None:
        return "unrated"
    theirs, mine = _rank_band(points), _rank_band(my_points)
    return "above" if theirs > mine else "below" if theirs < mine else "equal"


def _level_of(snap: int | None, player: Player | None, my_points: int) -> str | None:
    """Level of one match slot — at-match-time snapshot first, like the ELO."""
    if player is None:
        return None
    return level_from_points(snap if snap is not None else player.points, my_points)


def create_or_get_player(db: Session, payload: schemas.PlayerIn) -> schemas.PlayerOut:
    """Get-or-create by name. If the player exists, keep it.

    `level` is FROZEN legacy (2026-07-27): no longer written from payloads —
    analytics derive the relative level from points instead. New rows get the
    column default; the field is still accepted so old clients don't break."""
    name = (payload.name or "").strip()
    # Case-insensitive match, in Python: SQL `==` created duplicate people
    # ("ANNA" next to "Anna"), and SQLite lower() folds ASCII only ("Đức" vs
    # "đức" slipped through). NOT diacritic-folded on purpose — Tuấn and
    # Tuân are different names. Same rule as the rename guard below.
    existing = next(
        (p for p in db.query(Player).all() if (p.name or "").lower() == name.lower()),
        None,
    )
    if existing is None:
        existing = Player(
            name=name,
            note=payload.note,
            plays_pips=payload.plays_pips,
            points=payload.points,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)
    return player_to_out(existing)


def update_player(
    db: Session, player_id: int, payload: schemas.PlayerIn
) -> schemas.PlayerOut | None:
    p = db.get(Player, player_id)
    if p is None:
        return None
    # Renaming is safe by design: matches reference players by id, so every
    # historical display (grid, h2h, coach bundle) picks up the new name on
    # the next read. Renaming INTO an existing player's name is rejected —
    # two identical rows would be indistinguishable in the picker (a real
    # "same person twice" situation needs a merge feature, not a rename).
    new_name = (payload.name or "").strip()
    if new_name and new_name.lower() != (p.name or "").lower():
        # Python-side lower(): SQLite func.lower folds ASCII only, so a
        # rename to "đức" wasn't caught when "Đức" existed.
        clash = next(
            (
                x
                for x in db.query(Player).all()
                if x.id != player_id and (x.name or "").lower() == new_name.lower()
            ),
            None,
        )
        if clash is not None:
            raise Conflict(f'A player named "{clash.name}" already exists.')
    p.name = new_name or p.name
    # payload.level is ignored — the column is frozen legacy (see above).
    # None = caller doesn't manage the note (the picker's pips toggle sends a
    # placeholder player without one before its enrich lands — review find
    # 2026-08-09: it silently ERASED stored notes). Same guard as points.
    if payload.note is not None:
        p.note = payload.note
    p.plays_pips = payload.plays_pips
    # None = caller doesn't manage points (e.g. the picker's pips toggle) —
    # never wipe a rating the user set in the Database tab.
    resnapped: int | None = None
    if payload.points is not None:
        p.points = payload.points
        if payload.points_intent == "correction":
            resnapped = _refreeze_player_snapshots(db, player_id, payload.points)
    db.commit()
    db.refresh(p)
    out = player_to_out(p)
    out.resnapped_matches = resnapped
    return out


def _refreeze_player_snapshots(db: Session, player_id: int, points: int) -> int:
    """Correction path: the stored points were a TYPO, so every at-match-time
    snapshot of this player is wrong too — overwrite them all with the fixed
    value. ELO needs no explicit recalculation (the replay reads snapshots on
    every request). Only this player's slots are touched; the other players'
    snapshots in the same matches stay frozen. Returns the match count."""
    matches = (
        db.query(Match)
        .filter(
            or_(
                Match.opponent_id == player_id,
                Match.opponent2_id == player_id,
                Match.partner_id == player_id,
            )
        )
        .all()
    )
    for m in matches:
        if m.opponent_id == player_id:
            m.opp_points_snap = points
        if m.opponent2_id == player_id:
            m.opp2_points_snap = points
        if m.partner_id == player_id:
            m.partner_points_snap = points
    return len(matches)


def list_players_db(db: Session) -> schemas.PlayersDbResponse:
    """Every player + how often they appear in matches (the Database tab).

    Rated players first (highest points on top — a ranking table), unrated
    last alphabetically so they're easy to work through."""
    players = db.query(Player).all()
    # Two separate tallies: facing me (either opponent slot) vs on my side.
    vs_counts: dict[int, int] = {}
    with_counts: dict[int, int] = {}
    for col, counts in (
        (Match.opponent_id, vs_counts),
        (Match.opponent2_id, vs_counts),
        (Match.partner_id, with_counts),
    ):
        rows = (
            db.query(col, func.count(Match.id))
            # Playing matches only — the same rule as the per-player
            # drill-down, so a count badge always equals its modal rows.
            .filter(col.isnot(None), Match.is_nonplaying == False)  # noqa: E712
            .group_by(col)
            .all()
        )
        for pid, n in rows:
            counts[pid] = counts.get(pid, 0) + n
    ordered = sorted(
        players,
        key=lambda p: (
            p.points is None,  # rated first
            -(p.points or 0),
            p.name.lower(),
        ),
    )
    return schemas.PlayersDbResponse(
        players=[
            schemas.PlayerDbRow(
                **player_to_out(p).model_dump(),
                matches_vs=vs_counts.get(p.id, 0),
                matches_with=with_counts.get(p.id, 0),
            )
            for p in ordered
        ]
    )
