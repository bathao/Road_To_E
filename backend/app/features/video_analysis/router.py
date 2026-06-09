"""HTTP API for the Video Analysis tab (prefix /api/video)."""
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.video_analysis import analyzer, schemas, service

router = APIRouter(prefix="/api/video", tags=["video_analysis"])


# ------------------------------------------------------------------ health
@router.get("/health/model", response_model=schemas.ModelHealthOut)
def model_health():
    return analyzer.check_models()


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


@router.put("/skills/{aspect}", response_model=schemas.SkillOut)
def update_skill(aspect: str, payload: schemas.SkillIn, db: Session = Depends(get_db)):
    skill = service.update_skill(db, aspect, payload)
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
def get_report(db: Session = Depends(get_db)):
    return service.build_report(db)


# ------------------------------------------------------------------- clips
@router.post("/browse")
def browse_file(kind: str = Query("video", pattern="^(video|image)$")):
    """Pop a native file-open dialog on the local machine; return the picked
    path (empty string if the user cancels). kind = video | image."""
    return {"path": service.pick_video_file(kind)}


# ----------------------------------------------------- profile images (gallery)
@router.get("/profile/images", response_model=list[schemas.ProfileImageOut])
def list_profile_images(db: Session = Depends(get_db)):
    return service.list_profile_images(db)


@router.post("/profile/images", response_model=schemas.ProfileImageOut)
def add_profile_image(payload: schemas.ProfileImageIn, db: Session = Depends(get_db)):
    try:
        return service.add_profile_image_from_path(db, payload.local_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/profile/images/{image_id}", status_code=204)
def delete_profile_image(image_id: int, db: Session = Depends(get_db)):
    service.delete_profile_image(db, image_id)
    return Response(status_code=204)


@router.get("/profile/images/{image_id}/file")
def profile_image_file(image_id: int, db: Session = Depends(get_db)):
    img = service.get_profile_image(db, image_id)
    if img is None or not Path(img.path).is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(img.path)


@router.get("/clips/{clip_id}/frame")
def clip_frame(clip_id: int, db: Session = Depends(get_db)):
    """Full representative frame for the box-annotation GUI."""
    data = service.clip_frame_jpeg(db, clip_id)
    if not data:
        raise HTTPException(status_code=404, detail="Frame not available")
    return Response(content=data, media_type="image/jpeg")


@router.post("/clips/{clip_id}/crop-reference", response_model=schemas.ProfileImageOut)
def crop_reference(clip_id: int, payload: schemas.CropBoxIn, db: Session = Depends(get_db)):
    """Save a user-drawn box as a reference image (training the recogniser)."""
    img = service.add_reference_from_box(
        db, clip_id, payload.x, payload.y, payload.w, payload.h
    )
    if img is None:
        raise HTTPException(status_code=400, detail="Vùng cắt không hợp lệ hoặc clip không tồn tại.")
    return img


@router.get("/clips", response_model=list[schemas.ClipOut])
def list_clips(db: Session = Depends(get_db)):
    return service.list_clips(db)


@router.post("/clips", response_model=schemas.ClipOut)
def create_clip(
    payload: schemas.ClipCreateIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a clip from a file on disk (local-only tool). A long recording can
    be trimmed to a short segment via trim_start/trim_end (mm:ss or seconds);
    only the cut is kept as material. The source file is never modified."""
    p = Path(payload.local_path.strip().strip('"'))
    if not p.is_file():
        raise HTTPException(status_code=400, detail=f"Không tìm thấy file: {payload.local_path}")

    try:
        clip = service.create_clip(
            db,
            original_name=p.name,
            source_path=str(p),
            clip_type=payload.clip_type,
            focus=payload.focus,
            title=payload.title,
            note=payload.note,
            model=payload.model,
            trim_start=payload.trim_start,
            trim_end=payload.trim_end,
            me_side=payload.me_side,
            me_appearance=payload.me_appearance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:  # ffmpeg trim failure
        raise HTTPException(status_code=400, detail=str(exc))
    # Step 1: detect who the user is (no deep analysis yet).
    background.add_task(service.detect_clip, clip.id, payload.model)
    return clip


@router.post("/clips/{clip_id}/confirm", response_model=schemas.ClipOut)
def confirm_clip(clip_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    """User confirms the detected subject → start deep analysis."""
    clip = service.confirm_clip(db, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    background.add_task(service.analyze_clip, clip.id, clip.model or None)
    return clip


@router.post("/clips/{clip_id}/identify", response_model=schemas.ClipOut)
def identify_clip(
    clip_id: int,
    payload: schemas.IdentifyIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """User supplies/corrects who they are → go straight to deep analysis."""
    clip = service.identify_clip(db, clip_id, payload.me_side, payload.me_appearance)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    background.add_task(service.analyze_clip, clip.id, clip.model or None)
    return clip


@router.get("/clips/{clip_id}/evidence/{thumb}")
def clip_evidence(clip_id: int, thumb: str):
    """Serve an annotated evidence thumbnail (skeleton + angles) for a finding."""
    path = service.evidence_path(clip_id, thumb)
    if path is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(str(path))


@router.get("/clips/{clip_id}/preview")
def clip_preview(clip_id: int, db: Session = Depends(get_db)):
    clip = service.get_clip(db, clip_id)
    if clip is None or not clip.preview_path or not Path(clip.preview_path).is_file():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(clip.preview_path)


@router.get("/clips/{clip_id}", response_model=schemas.ClipDetailOut)
def get_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = service.get_clip(db, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return service.clip_detail_out(db, clip)


@router.post("/clips/{clip_id}/reanalyze", response_model=schemas.ClipOut)
def reanalyze_clip(
    clip_id: int,
    background: BackgroundTasks,
    payload: schemas.ReanalyzeIn | None = None,
    db: Session = Depends(get_db),
):
    model = payload.model if payload else None
    clip = service.start_reanalyze(db, clip_id, model)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    background.add_task(service.analyze_clip, clip.id, model)
    return clip


@router.post("/clips/{clip_id}/review", response_model=schemas.ClipDetailOut)
def review_clip(clip_id: int, payload: schemas.ReviewIn, db: Session = Depends(get_db)):
    """User confirms which findings are correct → only accepted ones count."""
    clip = service.review_clip(db, clip_id, payload)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return service.clip_detail_out(db, clip)


@router.post("/clips/{clip_id}/stop", response_model=schemas.ClipOut)
def stop_clip(clip_id: int, db: Session = Depends(get_db)):
    """Stop a running job (detect/analysis) for this clip."""
    clip = service.request_stop(db, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.delete("/clips/{clip_id}", status_code=204)
def delete_clip(clip_id: int, db: Session = Depends(get_db)):
    service.delete_clip(db, clip_id)
    return Response(status_code=204)


@router.get("/clips/{clip_id}/video")
def stream_video(clip_id: int, db: Session = Depends(get_db)):
    clip = service.get_clip(db, clip_id)
    if clip is None or not Path(clip.stored_path).is_file():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(clip.stored_path, filename=clip.original_name)
