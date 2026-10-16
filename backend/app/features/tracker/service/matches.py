"""Match output shape, events, handicap patterns, per-match ELO annotation.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.features.tracker import rating, schemas
from app.features.tracker.models import (
    Event,
    Match,
)

from .players import _level_of
from .tally import _NEWEST_FIRST, _playing_matches


def tournament_default_event(db: Session, entry_id: int | None) -> str | None:
    """Tournament matches default their Event to the tournament's name, so
    every existing event-chip display shows the tournament for free."""
    if entry_id is None:
        return None
    # Local import: the tournament feature is optional context for the
    # tracker — keep it out of this module's import graph.
    from app.features.tournament.models import TournamentEntry

    entry = db.get(TournamentEntry, entry_id)
    return entry.tournament.name if entry else None


def match_to_out(m: Match, my_points: int) -> schemas.MatchOut:
    """`my_points` = my CURRENT dynamic rating — the *_level fields are
    derived from points (at-match-time snapshot first), not the retired
    hand-picked label."""
    return schemas.MatchOut(
        id=m.id,
        date=m.date,
        category_id=m.category_id,
        discipline=m.discipline,
        best_of=m.best_of,
        my_sets=m.my_sets,
        opp_sets=m.opp_sets,
        event_id=m.event_id,
        event_name=m.event.name if m.event else None,
        is_nonplaying=m.is_nonplaying,
        nonplaying_label=m.nonplaying_label,
        note=m.note,
        order_index=m.order_index,
        opponent_id=m.opponent_id,
        opponent_name=m.opponent.name if m.opponent else None,
        opponent_level=_level_of(m.opp_points_snap, m.opponent, my_points),
        opponent_plays_pips=bool(m.opponent.plays_pips) if m.opponent else False,
        opponent2_id=m.opponent2_id,
        opponent2_name=m.opponent2.name if m.opponent2 else None,
        opponent2_level=_level_of(m.opp2_points_snap, m.opponent2, my_points),
        opponent2_plays_pips=bool(m.opponent2.plays_pips) if m.opponent2 else False,
        partner_id=m.partner_id,
        partner_name=m.partner.name if m.partner else None,
        partner_level=_level_of(m.partner_points_snap, m.partner, my_points),
        handicap=m.handicap or 0,
        handicap_pattern=m.handicap_pattern,
        tournament_entry_id=m.tournament_entry_id,
        round=m.round,
        # Tolerate a deleted entry (ALTER-added FK, not enforced): the match
        # simply loses its tournament label.
        tournament_name=(
            m.tournament_entry.tournament.name
            if m.tournament_entry_id and m.tournament_entry
            else None
        ),
    )


def get_or_create_event(db: Session, name: str | None) -> Event | None:
    name = (name or "").strip()
    if not name:
        return None
    event = db.query(Event).filter(Event.name == name).first()
    if event is None:
        event = Event(name=name)
        db.add(event)
        db.flush()
    return event


def normalize_handicap_pattern(raw: str | None) -> str | None:
    """"202" / "2-0-2" → "2-0-2". Uniform sequences ("222") and empty input
    collapse to None — the plain signed `handicap` int already carries a
    uniform per-set value, so only genuinely mixed ratios store a pattern."""
    digits = [c for c in (raw or "") if c.isdigit()]
    if not digits or len(set(digits)) == 1:
        return None
    return "-".join(digits)


def last_handicap_vs(db: Session, player_id: int) -> Match | None:
    """The most recent singles playing match against `player_id` — its
    handicap is the best guess for the next match's ratio (the GUI pre-fills
    it when the opponent is picked; the user can still change it)."""
    return (
        db.query(Match)
        .filter(
            Match.opponent_id == player_id,
            Match.discipline == "singles",
            Match.is_nonplaying == False,  # noqa: E712
        )
        .order_by(Match.date.desc(), Match.order_index.desc(), Match.id.desc())
        .first()
    )


def _annotate_elo(db: Session, matches: list[Match]) -> list[schemas.MatchOut]:
    """One replay pass → MatchOut per match, tagged with its ±Δ (counted) or
    the reason it doesn't move the rating (the GUI shows actionable "không
    tính"). The same pass yields my current rating for the derived *_level
    fields."""
    my_final, elo_steps = rating.replay(db)
    elo_deltas = {s.match_id: s.delta for s in elo_steps if s.match_id is not None}
    anchor_date = rating.get_my_anchor_date(db)
    outs = [match_to_out(m, round(my_final)) for m in matches]
    for out, m in zip(outs, matches, strict=True):
        if m.id in elo_deltas:
            out.elo_delta = round(elo_deltas[m.id], 1)
            out.elo_status = rating.STATUS_COUNTED
        else:
            out.elo_status = rating.skip_reason(m, anchor_date)
    return outs


def list_player_matches(db: Session, player_id: int) -> list[schemas.MatchOut]:
    """Every playing match involving `player_id` in ANY slot (opponent,
    second opponent, or my partner) — the Database tab's per-player
    drill-down. All-time, newest first, ELO-annotated like the week view."""
    matches = (
        _playing_matches(db)
        .filter(
            or_(
                Match.opponent_id == player_id,
                Match.opponent2_id == player_id,
                Match.partner_id == player_id,
            )
        )
        .order_by(*_NEWEST_FIRST)
        .all()
    )
    return _annotate_elo(db, matches)


# ------------------------------------------------------------- create / edit
def next_order(db: Session, date: dt.date, category_id: int) -> int:
    """Next free order_index in a cell — max+1, not count(), so the index
    stays unique after deletes/moves leave holes."""
    current_max = (
        db.query(Match.order_index)
        .filter(Match.date == date, Match.category_id == category_id)
        .order_by(Match.order_index.desc())
        .limit(1)
        .scalar()
    )
    return 0 if current_max is None else current_max + 1


def _apply_match_payload(db: Session, match: Match, payload: schemas.MatchIn) -> None:
    """Copy every editable field of the payload onto the row (order_index and
    the points snapshots are handled by the callers). Tournament matches with
    no explicit event default to the tournament's name, so event-based
    displays label them automatically."""
    event = get_or_create_event(
        db,
        payload.event_name or tournament_default_event(db, payload.tournament_entry_id),
    )
    match.date = payload.date
    match.category_id = payload.category_id
    match.discipline = payload.discipline
    match.best_of = payload.best_of
    match.my_sets = payload.my_sets
    match.opp_sets = payload.opp_sets
    match.event_id = event.id if event else None
    match.is_nonplaying = payload.is_nonplaying
    match.nonplaying_label = payload.nonplaying_label
    match.note = payload.note
    match.opponent_id = payload.opponent_id
    match.opponent2_id = payload.opponent2_id
    match.partner_id = payload.partner_id
    match.handicap = payload.handicap or 0
    match.handicap_pattern = normalize_handicap_pattern(payload.handicap_pattern)
    match.tournament_entry_id = payload.tournament_entry_id
    match.round = payload.round


def create_match(db: Session, payload: schemas.MatchIn) -> schemas.MatchOut:
    match = Match(
        order_index=(
            payload.order_index
            if payload.order_index is not None
            else next_order(db, payload.date, payload.category_id)
        ),
    )
    _apply_match_payload(db, match, payload)
    # Freeze the involved players' points at match time (ELO reads these).
    rating.snapshot_match_points(db, match)
    db.add(match)
    db.commit()
    db.refresh(match)
    return match_to_out(match, rating.compute_my_rating(db).current)


def update_match(db: Session, match_id: int, payload: schemas.MatchIn) -> schemas.MatchOut:
    match = db.get(Match, match_id)
    if match is None:
        raise NotFound("Match not found")
    prev_ids = (match.opponent_id, match.opponent2_id, match.partner_id)
    if (payload.date, payload.category_id) != (match.date, match.category_id):
        # Moved to another cell → append after that cell's existing matches so
        # order_index stays unique within the cell.
        match.order_index = next_order(db, payload.date, payload.category_id)
    _apply_match_payload(db, match, payload)
    # Re-snapshot points ONLY for slots whose player changed; editing a score
    # or date keeps the original at-match-time snapshots.
    rating.snapshot_match_points(db, match, prev_ids=prev_ids)
    db.commit()
    db.refresh(match)
    return match_to_out(match, rating.compute_my_rating(db).current)


def delete_match(db: Session, match_id: int) -> None:
    """Idempotent: deleting a missing match is not an error (the GUI's
    delete button may be pressed twice)."""
    obj = db.get(Match, match_id)
    if obj is not None:
        db.delete(obj)
        db.commit()
