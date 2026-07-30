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
from app.features.tracker.models import Player
from app.features.tracker.rating import (
    derive_placements,
    derive_warnings,
    placement_bonus,
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
) -> schemas.TournamentOut:
    return schemas.TournamentOut(
        id=t.id,
        name=t.name,
        location=t.location,
        start_date=t.start_date,
        end_date=t.end_date,
        level_limit=t.level_limit,
        note=t.note,
        entries=[_entry_out(e, players, placements, warnings) for e in t.entries],
    )


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
    """All tournaments: upcoming first (soonest on top), then past (newest
    first). "Past" = ended before today (end_date falls back to start_date)."""
    today = today or dt.date.today()
    rows = (
        db.query(Tournament)
        .options(selectinload(Tournament.entries).selectinload(TournamentEntry.members))
        .all()
    )
    players = _player_names(db, rows)

    def ends(t: Tournament) -> dt.date:
        return t.end_date or t.start_date

    upcoming = sorted((t for t in rows if ends(t) >= today), key=lambda t: t.start_date)
    past = sorted((t for t in rows if ends(t) < today), key=lambda t: t.start_date, reverse=True)
    placements = derive_placements(db)
    warnings = derive_warnings(db)
    return schemas.TournamentsResponse(
        tournaments=[
            _to_out(t, players, placements, warnings) for t in upcoming + past
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


# ------------------------------------------------------------- head coach view
def upcoming_for_coach(
    db: Session, today: dt.date | None = None, horizon_days: int = 90
) -> list[dict]:
    """Compact upcoming-tournament facts for the Head Coach bundle."""
    today = today or dt.date.today()
    resp = list_tournaments(db, today)
    out: list[dict] = []
    for t in resp.tournaments:
        ends = t.end_date or t.start_date
        if ends < today:
            break  # list is upcoming-first; the first past row ends the scan
        days_left = (t.start_date - today).days
        if days_left > horizon_days:
            continue
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
