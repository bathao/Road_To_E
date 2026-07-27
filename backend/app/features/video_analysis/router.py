"""HTTP API for the player profile engine (prefix /api/video, historical name).

Serves the Profile tab: identity + AI summary, confirmed findings (traits),
the skill ledger and the structured player report the Head Coach reads. The
paste-analysis intake pipeline was retired and its endpoints deleted
(2026-07-27); stored findings/reports data remains readable through /report.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.video_analysis import schemas, service

router = APIRouter(prefix="/api/video", tags=["video_analysis"])


# ----------------------------------------------------------------- profile
@router.get("/profile", response_model=schemas.ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    return service.get_or_create_profile(db)


@router.put("/profile", response_model=schemas.ProfileOut)
def put_profile(payload: schemas.ProfileIn, db: Session = Depends(get_db)):
    return service.update_profile(db, payload)


@router.post("/profile/regenerate-summary", response_model=schemas.ProfileOut)
def regenerate_summary(db: Session = Depends(get_db)):
    try:
        return service.regenerate_profile_summary(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ------------------------------------------------------------------ traits
@router.get("/traits", response_model=list[schemas.TraitOut])
def list_traits(
    aspect: str | None = Query(None),
    polarity: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return service.list_traits(db, aspect, polarity, status)


@router.post("/traits", response_model=schemas.TraitOut)
def create_trait(payload: schemas.TraitIn, db: Session = Depends(get_db)):
    return service.create_trait(db, payload)


@router.put("/traits/{trait_id}", response_model=schemas.TraitOut)
def update_trait(trait_id: int, payload: schemas.TraitIn, db: Session = Depends(get_db)):
    updated = service.update_trait(db, trait_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Trait not found")
    return updated


@router.delete("/traits/{trait_id}", status_code=204)
def delete_trait(trait_id: int, db: Session = Depends(get_db)):
    service.delete_trait(db, trait_id)
    return Response(status_code=204)


# ------------------------------------------------------- skill ledger + report
@router.get("/skills", response_model=list[schemas.SkillOut])
def list_skills(db: Session = Depends(get_db)):
    return service.list_skills(db)


@router.put("/skills/{setting}/{aspect}", response_model=schemas.SkillOut)
def update_skill(
    setting: str, aspect: str, payload: schemas.SkillIn, db: Session = Depends(get_db)
):
    skill = service.update_skill(db, aspect, setting, payload)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.post("/skills/regenerate", response_model=list[schemas.SkillOut])
def regenerate_skills(db: Session = Depends(get_db)):
    try:
        return service.regenerate_skills(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/report", response_model=schemas.ReportOut)
def get_player_report(db: Session = Depends(get_db)):
    return service.build_report(db)
