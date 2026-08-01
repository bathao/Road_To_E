"""Tournament CRUD + the compact "upcoming" view fed to the Head Coach."""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session, selectinload

from app.features.tournament import schemas
from app.features.tournament.models import (
    Tournament,
    TournamentEntry,
    TournamentEntryMember,
)
from app.features.tracker.models import Match, Player
from app.features.tracker.rating import (
    derive_placements,
    derive_round_reached,
    derive_warnings,
    placement_bonus,
    replay,
)

_DISCIPLINE_VI = {"singles": "đơn", "doubles": "đôi", "team": "đồng đội"}

# entry_id → (placement, deciding-match date), from rating.derive_placements.
_Placements = dict[int, tuple[str, dt.date]]


def _entry_out(
    e: TournamentEntry,
    players: dict[int, str],
    placements: _Placements,
    warnings: dict[int, str],
) -> schemas.EntryOut:
    teammate_ids = [m.player_id for m in e.members]
    placement = placements.get(e.id, (None,))[0]
    return schemas.EntryOut(
        id=e.id,
        discipline=e.discipline,
        partner_id=e.partner_id,
        partner_name=players.get(e.partner_id) if e.partner_id else None,
        teammate_ids=teammate_ids,
        teammate_names=[players.get(pid, "?") for pid in teammate_ids],
        team_members=e.team_members,
        division=e.division,
        final_placement=placement,
        bonus_points=placement_bonus(e.discipline, placement) or None,
        data_warning=warnings.get(e.id),
    )


def _to_out(
    t: Tournament,
    players: dict[int, str],
    placements: _Placements,
    warnings: dict[int, str],
    played: bool,
) -> schemas.TournamentOut:
    return schemas.TournamentOut(
        id=t.id,
        name=t.name,
        location=t.location,
        start_date=t.start_date,
        end_date=t.end_date,
        level_limit=t.level_limit,
        note=t.note,
        played=played,
        entries=[_entry_out(e, players, placements, warnings) for e in t.entries],
    )


def _linked_entry_ids(db: Session) -> set[int]:
    """Entry ids that already have at least one Daily Tracker match linked."""
    return {
        eid
        for (eid,) in db.query(Match.tournament_entry_id)
        .filter(Match.tournament_entry_id.isnot(None))
        .distinct()
        .all()
    }


def _is_played(t: Tournament, today: dt.date, linked: set[int]) -> bool:
    """Ended before today OR results already entered — entering a same-day
    tournament's results retires it immediately (user 2026-08-01)."""
    return (t.end_date or t.start_date) < today or any(
        e.id in linked for e in t.entries
    )


def _load_split(
    db: Session, today: dt.date
) -> tuple[list[Tournament], list[Tournament]]:
    """All tournaments split on the played rule: (upcoming soonest-first,
    played newest-first). The one loader behind the list AND the record."""
    rows = (
        db.query(Tournament)
        .options(selectinload(Tournament.entries).selectinload(TournamentEntry.members))
        .all()
    )
    linked = _linked_entry_ids(db)
    upcoming = sorted(
        (t for t in rows if not _is_played(t, today, linked)),
        key=lambda t: t.start_date,
    )
    played = sorted(
        (t for t in rows if _is_played(t, today, linked)),
        key=lambda t: t.start_date,
        reverse=True,
    )
    return upcoming, played


def _player_names(db: Session, tournaments: list[Tournament]) -> dict[int, str]:
    ids: set[int] = set()
    for t in tournaments:
        for e in t.entries:
            if e.partner_id is not None:
                ids.add(e.partner_id)
            ids.update(m.player_id for m in e.members)
    if not ids:
        return {}
    rows = db.query(Player.id, Player.name).filter(Player.id.in_(ids)).all()
    return dict(rows)


def list_tournaments(db: Session, today: dt.date | None = None) -> schemas.TournamentsResponse:
    """All tournaments: upcoming first (soonest on top), then played (newest
    first). "Played" = ended before today OR results already entered."""
    today = today or dt.date.today()
    upcoming, played = _load_split(db, today)
    players = _player_names(db, upcoming + played)
    placements = derive_placements(db)
    warnings = derive_warnings(db)
    return schemas.TournamentsResponse(
        tournaments=[
            _to_out(t, players, placements, warnings, played=False)
            for t in upcoming
        ]
        + [
            _to_out(t, players, placements, warnings, played=True)
            for t in played
        ]
    )


def _apply(t: Tournament, payload: schemas.TournamentIn) -> None:
    t.name = payload.name.strip()
    t.location = (payload.location or "").strip() or None
    t.start_date = payload.start_date
    # A single-day tournament stores end_date = None; reject end < start by
    # silently clamping (the GUI already prevents it — this is a data guard).
    t.end_date = (
        payload.end_date
        if payload.end_date and payload.end_date > payload.start_date
        else None
    )
    t.level_limit = (payload.level_limit or "").strip() or None
    t.note = (payload.note or "").strip() or None
    t.entries = [
        TournamentEntry(
            discipline=e.discipline,
            partner_id=e.partner_id if e.discipline == "doubles" else None,
            team_members=(e.team_members or "").strip() or None
            if e.discipline == "team"
            else None,
            division=(e.division or "").strip() or None,
            members=[
                TournamentEntryMember(player_id=pid)
                for pid in (e.teammate_ids if e.discipline == "team" else [])
            ],
        )
        for e in payload.entries
    ]


def create_tournament(db: Session, payload: schemas.TournamentIn) -> schemas.TournamentsResponse:
    t = Tournament(name="", start_date=payload.start_date)
    _apply(t, payload)
    db.add(t)
    db.commit()
    return list_tournaments(db)


def update_tournament(
    db: Session, tournament_id: int, payload: schemas.TournamentIn
) -> schemas.TournamentsResponse:
    t = db.get(Tournament, tournament_id)
    if t is None:
        raise LookupError("Tournament not found")
    _apply(t, payload)  # entries are fully replaced (delete-orphan cascade)
    db.commit()
    return list_tournaments(db)


def delete_tournament(db: Session, tournament_id: int) -> schemas.TournamentsResponse:
    t = db.get(Tournament, tournament_id)
    if t is not None:
        db.delete(t)
        db.commit()
    return list_tournaments(db)


# ------------------------------------------- tournament record (Profile tab)
def build_record(db: Session, today: dt.date | None = None) -> schemas.TournamentRecordResponse:
    """Read-only history of PLAYED tournaments (newest first): how far each
    entry got + its W-L record + every entered match, all derived from the
    Daily Tracker matches linked via tournament_entry_id. Nothing stored.

    "Played" = ended before today OR any match already linked — the same
    rule the Daily Tracker filters on: entering a same-day tournament's
    results moves it here immediately, not tomorrow (user 2026-08-01)."""
    today = today or dt.date.today()
    _, past = _load_split(db, today)
    if not past:
        return schemas.TournamentRecordResponse()

    players = _player_names(db, past)
    placements = derive_placements(db)
    warnings = derive_warnings(db)
    reached = derive_round_reached(db)

    entry_ids = [e.id for t in past for e in t.entries]
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_entry_id.in_(entry_ids),
            Match.is_nonplaying == False,  # noqa: E712
        )
        .order_by(Match.date, Match.order_index, Match.id)
        .all()
    ) if entry_ids else []
    by_entry: dict[int, list[Match]] = {}
    for m in matches:
        by_entry.setdefault(m.tournament_entry_id, []).append(m)

    # One replay for the per-match ±Δ annotations (bonus steps have no match).
    _, steps = replay(db)
    delta_by_match = {s.match_id: s.delta for s in steps if s.match_id is not None}

    def _record_match(m: Match) -> schemas.RecordMatch:
        delta = delta_by_match.get(m.id)
        return schemas.RecordMatch(
            id=m.id,
            date=m.date,
            round=m.round,
            discipline=m.discipline,
            opponent_name=m.opponent.name if m.opponent else None,
            opponent2_name=m.opponent2.name if m.opponent2 else None,
            partner_name=m.partner.name if m.partner else None,
            my_sets=m.my_sets,
            opp_sets=m.opp_sets,
            won=None if m.my_sets == m.opp_sets else m.my_sets > m.opp_sets,
            elo_delta=round(delta, 1) if delta is not None else None,
        )

    def _record_entry(e: TournamentEntry) -> schemas.RecordEntry:
        ms = by_entry.get(e.id, [])
        decided = [m for m in ms if m.my_sets != m.opp_sets]
        rnd, won = reached.get(e.id, (None, False))
        return schemas.RecordEntry(
            entry=_entry_out(e, players, placements, warnings),
            round_reached=rnd,
            reached_won=won,
            wins=sum(1 for m in decided if m.my_sets > m.opp_sets),
            losses=sum(1 for m in decided if m.my_sets < m.opp_sets),
            matches=[_record_match(m) for m in ms],
        )

    return schemas.TournamentRecordResponse(
        tournaments=[
            schemas.RecordTournament(
                id=t.id,
                name=t.name,
                location=t.location,
                start_date=t.start_date,
                end_date=t.end_date,
                entries=[_record_entry(e) for e in t.entries],
            )
            for t in past
        ]
    )


# ------------------------------------------------------------- head coach view
def upcoming_for_coach(
    db: Session, today: dt.date | None = None, horizon_days: int = 90
) -> list[dict]:
    """Compact upcoming-tournament facts for the Head Coach bundle."""
    today = today or dt.date.today()
    resp = list_tournaments(db, today)
    out: list[dict] = []
    for t in resp.tournaments:
        if t.played:
            break  # list is upcoming-first; the first played row ends the
            # scan (incl. a same-day tournament whose results are already in)
        days_left = (t.start_date - today).days
        if days_left > horizon_days:
            break  # upcoming is sorted soonest-first — the rest are further out
        entries = []
        for e in t.entries:
            label = _DISCIPLINE_VI.get(e.discipline, e.discipline)
            if e.discipline == "doubles" and e.partner_name:
                label += f" (đánh cặp với {e.partner_name})"
            if e.discipline == "team":
                # Team name/note and the picked roster, whichever exist.
                parts = [p for p in (e.team_members, ", ".join(e.teammate_names)) if p]
                if parts:
                    label += f" ({' — '.join(parts)})"
            if e.division:
                label += f" — {e.division}"
            entries.append(label)
        out.append(
            {
                "name": t.name,
                "start_date": t.start_date.isoformat(),
                "days_left": days_left,  # 0 = today; negative = running now
                "location": t.location or "",
                "level_limit": t.level_limit or "",
                "entries": entries,
                "note": t.note or "",
            }
        )
    return out
