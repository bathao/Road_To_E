"""HTTP API for tournaments (prefix /api/tournaments)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.tournament import schemas, service

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


@router.get("", response_model=schemas.TournamentsResponse)
def list_tournaments(db: Session = Depends(get_db)):
    """All tournaments: upcoming first (soonest on top), then past (newest first)."""
    return service.list_tournaments(db)


@router.get("/record", response_model=schemas.TournamentRecordResponse)
def get_record(db: Session = Depends(get_db)):
    """Read-only history of PLAYED tournaments for the Profile tab (ended,
    or with matches already entered — a same-day tournament shows up as soon
    as its results go in): how far each entry got, its W-L record, and the
    entered matches behind it — all derived, nothing stored."""
    return service.build_record(db)


@router.post("", response_model=schemas.TournamentsResponse)
def create_tournament(payload: schemas.TournamentIn, db: Session = Depends(get_db)):
    return service.create_tournament(db, payload)


@router.put("/{tournament_id}", response_model=schemas.TournamentsResponse)
def update_tournament(
    tournament_id: int, payload: schemas.TournamentIn, db: Session = Depends(get_db)
):
    try:
        return service.update_tournament(db, tournament_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Tournament not found")


@router.delete("/{tournament_id}", response_model=schemas.TournamentsResponse)
def delete_tournament(tournament_id: int, db: Session = Depends(get_db)):
    """Returns the remaining list (NOT 204 — a 204 body reads as `undefined`
    in the frontend api client, which is also useMutate's failure sentinel)."""
    return service.delete_tournament(db, tournament_id)
