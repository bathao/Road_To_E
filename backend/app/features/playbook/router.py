"""HTTP API for the Tactical Playbook tab (prefix /api/playbook)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.playbook import schemas, service

router = APIRouter(prefix="/api/playbook", tags=["playbook"])


# ---------------------------------------------------------------- meta / library
@router.get("/meta", response_model=schemas.PlaybookMeta)
def get_meta():
    """Phases + suggested tag/opponent chips (shared by the editor and library)."""
    return service.get_meta()


@router.get("/library", response_model=list[schemas.LibraryItem])
def get_library():
    """The built-in catalog of general tactics (browse-only reference)."""
    return service.get_library()


# ---------------------------------------------------------------- my tactics
@router.get("/tactics", response_model=list[schemas.TacticOut])
def list_tactics(db: Session = Depends(get_db)):
    return service.list_tactics(db)


@router.post("/tactics", response_model=schemas.TacticOut)
def create_tactic(payload: schemas.TacticIn, db: Session = Depends(get_db)):
    """Create a tactic — hand-entered, or a Library copy carrying source_key."""
    return service.create_tactic(db, payload)


@router.put("/tactics/reorder")
def reorder_tactics(payload: schemas.ReorderIn, db: Session = Depends(get_db)):
    service.reorder(db, payload.ids)
    return {"ok": True}


@router.put("/tactics/{tactic_id}", response_model=schemas.TacticOut)
def update_tactic(
    tactic_id: int, payload: schemas.TacticIn, db: Session = Depends(get_db)
):
    updated = service.update_tactic(db, tactic_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Tactic not found")
    return updated


@router.delete("/tactics/{tactic_id}", status_code=204)
def delete_tactic(tactic_id: int, db: Session = Depends(get_db)):
    if not service.delete_tactic(db, tactic_id):
        raise HTTPException(status_code=404, detail="Tactic not found")
    return Response(status_code=204)
