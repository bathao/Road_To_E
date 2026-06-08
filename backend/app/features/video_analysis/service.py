"""Business logic for the Video Analysis tab: file handling, the background
analysis job, trait accumulation and profile synthesis."""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.settings import PROFILE_REFS_DIR, VIDEOS_DIR
from app.features.video_analysis import analyzer, schemas
from app.features.video_analysis.models import (
    VAAnalysis,
    VAClip,
    VAProfile,
    VAProfileImage,
    VASkill,
    VATrait,
)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

ALLOWED_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# --------------------------------------------------------- native file picker
def pick_video_file(kind: str = "video") -> str:
    """Open a native OS file-open dialog on the machine running the server (this
    is a local-only tool) and return the chosen absolute path, or "" if
    cancelled. Run in a short-lived subprocess so Tkinter never touches the
    server's threads. ``kind`` is 'video' or 'image'."""
    if kind == "image":
        title = "Chọn ảnh nhận diện"
        types = "[('Ảnh', '*.jpg *.jpeg *.png *.webp *.bmp'), ('Tất cả', '*.*')]"
    else:
        title = "Chọn video để phân tích"
        types = "[('Video', '*.mp4 *.mov *.m4v *.avi *.mkv *.webm'), ('Tất cả', '*.*')]"
    code = (
        # Make the picker DPI-aware so the native dialog renders crisp. Prefer
        # Per-Monitor-v2 (crisp system dialogs); fall back to v1 / system-aware.
        "import ctypes\n"
        "def _dpi():\n"
        "    try:\n"
        "        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)); return\n"
        "    except Exception: pass\n"
        "    try:\n"
        "        ctypes.windll.shcore.SetProcessDpiAwareness(2); return\n"
        "    except Exception: pass\n"
        "    try: ctypes.windll.user32.SetProcessDPIAware()\n"
        "    except Exception: pass\n"
        "_dpi()\n"
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
        f"p = filedialog.askopenfilename(title={title!r}, filetypes={types})\n"
        "r.destroy()\n"
        "print(p or '')\n"
    )
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return ""
    return (proc.stdout or "").strip()


# ----------------------------------------------------------------- profile
def get_or_create_profile(db: Session) -> VAProfile:
    profile = db.get(VAProfile, 1)
    if profile is None:
        profile = VAProfile(id=1, name="Nguyễn Bá Thảo")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, payload: schemas.ProfileIn) -> VAProfile:
    profile = get_or_create_profile(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


def regenerate_profile_summary(db: Session) -> VAProfile:
    """Fold all *accepted* findings into the profile summary fields via the LLM."""
    profile = get_or_create_profile(db)
    traits = [
        {"aspect": t.aspect, "polarity": t.polarity, "text": t.text}
        for t in db.query(VATrait)
        .filter(VATrait.status == "accepted")
        .order_by(VATrait.created_at)
        .all()
    ]
    basics = {"handed": profile.handed, "grip": profile.grip, "style": profile.style}
    result = analyzer.synthesize_profile(basics, traits)
    for field in (
        "serve_summary", "footwork_summary", "posture_summary",
        "strengths_summary", "weaknesses_summary", "overall_summary",
    ):
        if field in result:
            setattr(profile, field, result[field])
    db.commit()
    db.refresh(profile)
    return profile


# --------------------------------------------------------- profile images
def list_profile_images(db: Session) -> list[VAProfileImage]:
    return db.query(VAProfileImage).order_by(VAProfileImage.created_at.desc()).all()


def add_profile_image_from_path(db: Session, src_path: str) -> VAProfileImage:
    p = Path(src_path.strip().strip('"'))
    if not p.is_file():
        raise ValueError(f"Không tìm thấy ảnh: {src_path}")
    if p.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"Định dạng ảnh không hỗ trợ: {p.suffix}")
    dst = PROFILE_REFS_DIR / f"{uuid.uuid4().hex}{p.suffix.lower()}"
    shutil.copy2(str(p), str(dst))
    img = VAProfileImage(path=str(dst), source_clip_id=None)
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


def _save_ref_crops(db: Session, crops_b64: list[str], clip_id: int) -> None:
    """Persist auto-generated reference crops (b64 JPEG) for a labelled clip."""
    for b64 in crops_b64:
        try:
            data = base64.b64decode(b64)
        except (ValueError, TypeError):
            continue
        dst = PROFILE_REFS_DIR / f"{uuid.uuid4().hex}.jpg"
        dst.write_bytes(data)
        db.add(VAProfileImage(path=str(dst), source_clip_id=clip_id))


def latest_reference_b64(db: Session, limit: int = 4) -> list[str]:
    """Most-recent reference images as base64, to feed the VLM for matching."""
    imgs = (
        db.query(VAProfileImage)
        .order_by(VAProfileImage.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[str] = []
    for img in imgs:
        try:
            out.append(base64.b64encode(Path(img.path).read_bytes()).decode("ascii"))
        except OSError:
            continue
    return out


def clip_frame_jpeg(db: Session, clip_id: int) -> bytes | None:
    """Full representative frame of a clip (for the box-annotation GUI)."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return None
    return analyzer.frame_jpeg(clip.stored_path)


def add_reference_from_box(db: Session, clip_id: int, x: float, y: float,
                           w: float, h: float) -> VAProfileImage | None:
    """Crop a user-drawn box from the clip's frame, save it as a reference image
    (training data for future identification) and use it as the clip's preview."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return None
    data = analyzer.crop_box_jpeg(clip.stored_path, x, y, w, h)
    if not data:
        return None
    gallery = PROFILE_REFS_DIR / f"{uuid.uuid4().hex}.jpg"
    gallery.write_bytes(data)
    img = VAProfileImage(path=str(gallery), source_clip_id=clip_id)
    db.add(img)
    # Reflect the hand-drawn box as this clip's confirmation thumbnail too.
    if clip.preview_path:
        try:
            Path(clip.preview_path).unlink(missing_ok=True)
        except OSError:
            pass
    preview = VIDEOS_DIR / f"preview_{uuid.uuid4().hex}.jpg"
    preview.write_bytes(data)
    clip.preview_path = str(preview)
    db.commit()
    db.refresh(img)
    return img


def delete_profile_image(db: Session, image_id: int) -> None:
    img = db.get(VAProfileImage, image_id)
    if img:
        try:
            Path(img.path).unlink(missing_ok=True)
        except OSError:
            pass
        db.delete(img)
        db.commit()


def get_profile_image(db: Session, image_id: int) -> VAProfileImage | None:
    return db.get(VAProfileImage, image_id)


# --------------------------------------------------------- traits / findings
def list_traits(
    db: Session, aspect: str | None, polarity: str | None, status: str | None = None
) -> list[VATrait]:
    query = db.query(VATrait)
    if aspect:
        query = query.filter(VATrait.aspect == aspect)
    if polarity:
        query = query.filter(VATrait.polarity == polarity)
    if status:
        query = query.filter(VATrait.status == status)
    return query.order_by(VATrait.created_at.desc()).all()


def create_trait(db: Session, payload: schemas.TraitIn) -> VATrait:
    # A manually-entered finding is authoritative → accepted straight away.
    trait = VATrait(
        aspect=payload.aspect,
        polarity=payload.polarity,
        text=payload.text,
        confidence=payload.confidence,
        status="accepted",
        reviewed_at=_utcnow(),
        source_clip_id=None,  # manual entry
    )
    db.add(trait)
    db.commit()
    db.refresh(trait)
    return trait


def update_trait(db: Session, trait_id: int, payload: schemas.TraitIn) -> VATrait | None:
    trait = db.get(VATrait, trait_id)
    if trait is None:
        return None
    trait.aspect = payload.aspect
    trait.polarity = payload.polarity
    trait.text = payload.text
    trait.confidence = payload.confidence
    db.commit()
    db.refresh(trait)
    return trait


def delete_trait(db: Session, trait_id: int) -> None:
    trait = db.get(VATrait, trait_id)
    if trait:
        db.delete(trait)
        db.commit()


# ------------------------------------------------------------------- clips
def list_clips(db: Session) -> list[VAClip]:
    return db.query(VAClip).order_by(VAClip.created_at.desc()).all()


def parse_time(s: str | None) -> float | None:
    """Parse a timestamp into seconds. Accepts 'SS', 'MM:SS', 'HH:MM:SS' with
    optional decimals. Empty/None -> None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        if ":" in s:
            sec = 0.0
            for part in s.split(":"):
                sec = sec * 60 + float(part)
            return sec
        return float(s)
    except ValueError:
        raise ValueError(f"Thời gian không hợp lệ: '{s}' (dùng dạng mm:ss hoặc giây)")


SIDE_VALUES = {"left", "right", "top", "bottom", "alone", ""}


def create_clip(db: Session, *, original_name: str, source_path: str,
                clip_type: str, title: str, note: str | None,
                model: str | None, trim_start: str | None = None,
                trim_end: str | None = None, me_side: str = "",
                me_appearance: str = "") -> VAClip:
    """Persist a clip from ``source_path`` (a file on disk). When a trim range
    is given, cut that segment out and keep only the short cut as material;
    otherwise copy the whole file. The source file is never modified."""
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"Định dạng không hỗ trợ: {suffix or '(không có)'}")

    start = parse_time(trim_start)
    end = parse_time(trim_end)
    trimming = start is not None or end is not None
    label = title or Path(original_name).stem

    if trimming:
        if start is None or end is None:
            raise ValueError("Cần nhập cả thời gian bắt đầu và kết thúc để cắt.")
        if end <= start:
            raise ValueError("Thời gian kết thúc phải lớn hơn bắt đầu.")
        stored = VIDEOS_DIR / f"{uuid.uuid4().hex}.mp4"
        analyzer.trim_segment(source_path, start, end, str(stored))
        label = title or f"{Path(original_name).stem} [{trim_start}–{trim_end}]"
    else:
        stored = VIDEOS_DIR / f"{uuid.uuid4().hex}{suffix}"
        shutil.copy2(source_path, str(stored))

    meta = {}
    try:
        meta = analyzer.probe(str(stored))
    except Exception:
        meta = {}

    clip = VAClip(
        original_name=original_name,
        stored_path=str(stored),
        clip_type=clip_type if clip_type in ("training", "match_points") else "training",
        title=label,
        note=note,
        duration_sec=meta.get("duration_sec"),
        fps=meta.get("fps"),
        width=meta.get("width"),
        height=meta.get("height"),
        model=model or "",
        status="processing",
        processing_started_at=_utcnow(),
        me_side=me_side if me_side in SIDE_VALUES else "",
        me_appearance=me_appearance or "",
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def get_clip(db: Session, clip_id: int) -> VAClip | None:
    return db.get(VAClip, clip_id)


def delete_clip(db: Session, clip_id: int) -> bool:
    """Delete the clip, its file, analysis and clip-sourced traits (cascade)."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return False
    for path in (clip.stored_path, clip.preview_path):
        if path:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
    db.delete(clip)
    db.commit()
    return True


_CONCRETE_SIDES = ("left", "right", "top", "bottom")


def confirm_clip(db: Session, clip_id: int) -> VAClip | None:
    """User confirms the detected subject → move to deep analysis."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return None
    clip.status = "analyzing"
    clip.error_msg = None
    clip.processing_started_at = _utcnow()
    db.commit()
    db.refresh(clip)
    return clip


def identify_clip(db: Session, clip_id: int, me_side: str, me_appearance: str) -> VAClip | None:
    """User supplies / corrects who they are, then go straight to deep analysis
    (the user is authoritative, no need to re-confirm)."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return None
    clip.me_side = me_side if me_side in SIDE_VALUES else ""
    clip.me_appearance = me_appearance or ""
    clip.identified = True
    clip.status = "analyzing"
    clip.error_msg = None
    clip.processing_started_at = _utcnow()
    db.commit()
    db.refresh(clip)
    return clip


def start_reanalyze(db: Session, clip_id: int, model: str | None) -> VAClip | None:
    """Re-run the deep analysis with the already-known subject."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return None
    clip.status = "analyzing"
    clip.error_msg = None
    clip.processing_started_at = _utcnow()
    if model:
        clip.model = model
    db.commit()
    db.refresh(clip)
    return clip


def _set_preview(db: Session, clip: VAClip, b64: str | None) -> None:
    if not b64:
        return
    try:
        data = base64.b64decode(b64)
    except (ValueError, TypeError):
        return
    dst = VIDEOS_DIR / f"preview_{uuid.uuid4().hex}.jpg"
    dst.write_bytes(data)
    if clip.preview_path:
        try:
            Path(clip.preview_path).unlink(missing_ok=True)
        except OSError:
            pass
    clip.preview_path = str(dst)


# ------------------------------------------------------------------ stop
# A background job (detect / deep analysis) runs in a worker thread and may be
# blocked in a long Ollama call we can't forcibly interrupt. "Stop" works
# cooperatively: it flips the clip to "stopped" (the UI frees immediately) and
# records the id here; the worker checks this after its heavy step and discards
# its result instead of saving — so no stale analysis is written.
import threading

_STOP_LOCK = threading.Lock()
_STOP_REQUESTS: set[int] = set()
_STOPPABLE = {"pending", "processing", "analyzing"}


def _stop_requested(clip_id: int) -> bool:
    with _STOP_LOCK:
        return clip_id in _STOP_REQUESTS


def _clear_stop(clip_id: int) -> None:
    with _STOP_LOCK:
        _STOP_REQUESTS.discard(clip_id)


def request_stop(db: Session, clip_id: int) -> VAClip | None:
    """Ask a running job to stop. Only meaningful while pending/processing/
    analyzing; otherwise returns the clip unchanged."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return None
    if clip.status in _STOPPABLE:
        with _STOP_LOCK:
            _STOP_REQUESTS.add(clip_id)
        clip.status = "stopped"
        clip.error_msg = None
        clip.processing_started_at = None
        db.commit()
        db.refresh(clip)
    return clip


# ----------------------------------------- step 1: detect (background job)
def detect_clip(clip_id: int, model: str | None) -> None:
    """Locate the user in the clip (no deep analysis). Ends in awaiting_confirm
    (found → ask user to confirm) or needs_id (couldn't place → ask for info)."""
    db = SessionLocal()
    try:
        clip = db.get(VAClip, clip_id)
        if clip is None:
            return
        if clip.status != "processing":  # stopped before we started
            return
        profile = get_or_create_profile(db)
        refs = latest_reference_b64(db)
        try:
            if clip.me_side in _CONCRETE_SIDES or clip.me_side == "alone":
                # User already told us where they are — trust it, just preview.
                side = clip.me_side
                clip.identified = True
                clip.subject_desc = (
                    "một mình trong clip" if side == "alone"
                    else f"(bạn đã chọn) phía {side}"
                    + (f", {clip.me_appearance}" if clip.me_appearance else "")
                )
            else:
                det = analyzer.detect_subject(
                    clip.stored_path, reference_images_b64=refs,
                    me_side=clip.me_side, me_appearance=clip.me_appearance,
                    handed=profile.handed, model=model,
                )
                side = det.get("side", "unknown")
                ok = bool(det.get("identified")) and side in _CONCRETE_SIDES
                clip.identified = ok
                clip.subject_desc = (det.get("subject") or "")[:500] or None
                if ok:
                    clip.me_side = side
                    if det.get("appearance") and not clip.me_appearance:
                        clip.me_appearance = det["appearance"][:200]
                if not ok:
                    clip.status = "needs_id"
                    db.commit()
                    return
        except Exception as exc:
            clip.status = "error"
            clip.error_msg = str(exc)[:1000]
            db.commit()
            return

        if _stop_requested(clip_id):  # user stopped during detection
            return

        # Found → build a preview crop and wait for the user to confirm.
        try:
            _set_preview(db, clip, analyzer.make_preview_b64(clip.stored_path, side))
        except Exception:
            pass
        clip.status = "awaiting_confirm"
        db.commit()
    finally:
        _clear_stop(clip_id)
        db.close()


# ----------------------------------- step 2: deep analysis (background job)
def analyze_clip(clip_id: int, model: str | None) -> None:
    """Deep technique analysis of the confirmed subject; saves analysis, traits,
    and grows the reference gallery from the (now confirmed) labelled clip."""
    db = SessionLocal()
    try:
        clip = db.get(VAClip, clip_id)
        if clip is None:
            return
        if clip.status != "analyzing":  # stopped before we started
            return
        profile = get_or_create_profile(db)
        refs = latest_reference_b64(db)
        try:
            result = analyzer.analyze_file(
                clip.stored_path, clip.clip_type, model or (clip.model or None),
                me_side=clip.me_side, me_appearance=clip.me_appearance,
                handed=profile.handed, reference_images_b64=refs,
            )
        except Exception as exc:
            clip.status = "error"
            clip.error_msg = str(exc)[:1000]
            db.commit()
            return

        if _stop_requested(clip_id):  # user stopped during analysis → discard
            return

        raw = result["raw"]
        clip.model = result["model"]
        clip.frames_sampled = result.get("frames_sampled")
        if raw.get("subject"):
            clip.subject_desc = raw["subject"][:500]
        clip.status = "done"

        db.query(VAAnalysis).filter(VAAnalysis.clip_id == clip_id).delete()
        db.add(VAAnalysis(
            clip_id=clip_id,
            model=result["model"],
            language="vi",
            summary=result.get("summary", ""),
            raw_json=json.dumps(raw, ensure_ascii=False),
            pose_json=json.dumps(result.get("pose", {}), ensure_ascii=False),
        ))

        # Findings start as 'proposed' — they only count once the user reviews
        # and confirms them (see review_clip). Re-analysing replaces them.
        db.query(VATrait).filter(VATrait.source_clip_id == clip_id).delete()
        for polarity, key in (("strength", "strengths"), ("weakness", "weaknesses")):
            for item in raw.get(key, []) or []:
                text = (item.get("text") or "").strip()
                if not text:
                    continue
                db.add(VATrait(
                    aspect=item.get("aspect", "other"),
                    polarity=polarity,
                    text=text,
                    ai_text=text,
                    status="proposed",
                    source_clip_id=clip_id,
                ))
        clip.reviewed_at = None  # fresh analysis → needs review again

        # Grow the reference gallery from this confirmed-and-cropped clip.
        if clip.me_side in _CONCRETE_SIDES:
            _save_ref_crops(db, result.get("ref_crops_b64", []), clip_id)
        db.commit()
    finally:
        _clear_stop(clip_id)
        db.close()


# ------------------------------------------------------------ serialisation
def analysis_to_out(a: VAAnalysis) -> schemas.AnalysisOut:
    def _load(s: str) -> dict:
        try:
            return json.loads(s) if s else {}
        except json.JSONDecodeError:
            return {}

    return schemas.AnalysisOut(
        id=a.id,
        clip_id=a.clip_id,
        model=a.model,
        language=a.language,
        summary=a.summary,
        raw=_load(a.raw_json),
        pose=_load(a.pose_json),
        created_at=a.created_at,
    )


def clip_detail_out(db: Session, clip: VAClip) -> schemas.ClipDetailOut:
    # Validate the flat clip fields only; the analysis relationship is mapped
    # by hand because its ORM columns (raw_json/pose_json) differ from the
    # response shape (raw/pose).
    base = schemas.ClipOut.model_validate(clip)
    return schemas.ClipDetailOut(
        **base.model_dump(),
        analysis=analysis_to_out(clip.analysis) if clip.analysis else None,
        traits=[
            schemas.TraitOut.model_validate(t)
            for t in sorted(clip.traits, key=lambda t: (t.polarity, t.id))
        ],
    )


# ----------------------------------------------------------- review a clip
def review_clip(db: Session, clip_id: int, payload: schemas.ReviewIn) -> VAClip | None:
    """Apply the user's accept/reject (and edits) to this clip's findings, then
    mark the clip reviewed. Only accepted findings count towards the profile."""
    clip = db.get(VAClip, clip_id)
    if clip is None:
        return None
    by_id = {t.id: t for t in clip.traits}
    now = _utcnow()
    for d in payload.decisions:
        trait = by_id.get(d.id)
        if trait is None:
            continue
        trait.status = "accepted" if d.accept else "rejected"
        trait.reviewed_at = now
        if d.text is not None and d.text.strip():
            trait.text = d.text.strip()
        if d.aspect:
            trait.aspect = d.aspect
        if d.polarity:
            trait.polarity = d.polarity
    clip.reviewed_at = now
    db.commit()
    db.refresh(clip)
    return clip


# ------------------------------------------------------------- skill ledger
def list_skills(db: Session) -> list[VASkill]:
    """The skill ledger ordered by the canonical aspect order."""
    order = {a: i for i, a in enumerate(schemas.SKILL_ASPECTS)}
    skills = db.query(VASkill).all()
    return sorted(skills, key=lambda s: order.get(s.aspect, 99))


def update_skill(db: Session, aspect: str, payload: schemas.SkillIn) -> VASkill | None:
    skill = db.query(VASkill).filter(VASkill.aspect == aspect).first()
    if skill is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    db.commit()
    db.refresh(skill)
    return skill


def _accepted_findings_by_aspect(db: Session) -> dict[str, list[VATrait]]:
    grouped: dict[str, list[VATrait]] = {}
    rows = (
        db.query(VATrait)
        .filter(VATrait.status == "accepted")
        .order_by(VATrait.created_at)
        .all()
    )
    for t in rows:
        # Fold the catch-all 'other' into the closest skill bucket only if it is
        # a real skill aspect; otherwise skip it for the ledger.
        if t.aspect not in schemas.SKILL_ASPECTS:
            continue
        grouped.setdefault(t.aspect, []).append(t)
    return grouped


def regenerate_skills(db: Session) -> list[VASkill]:
    """Synthesise the skill ledger from accepted findings via the local LLM."""
    profile = get_or_create_profile(db)
    grouped = _accepted_findings_by_aspect(db)
    findings_by_aspect = {
        aspect: [{"polarity": t.polarity, "text": t.text} for t in items]
        for aspect, items in grouped.items()
    }
    basics = {"handed": profile.handed, "grip": profile.grip, "style": profile.style}
    results = analyzer.synthesize_skills(basics, findings_by_aspect)

    by_aspect = {s.aspect: s for s in db.query(VASkill).all()}
    now = _utcnow()
    for item in results:
        aspect = item.get("aspect")
        skill = by_aspect.get(aspect)
        if skill is None or aspect not in schemas.SKILL_ASPECTS:
            continue
        rating = item.get("rating")
        if isinstance(rating, int):
            skill.rating = max(1, min(10, rating))
        status = item.get("status")
        if status in schemas.SKILL_STATUSES:
            skill.status = status
        if item.get("assessment"):
            skill.assessment = item["assessment"]
        priority = item.get("priority")
        skill.priority = priority if isinstance(priority, int) and priority > 0 else None
        skill.updated_at = now
    db.commit()
    return list_skills(db)


# --------------------------------------------------- structured player report
def build_report(db: Session) -> schemas.ReportOut:
    """The systematic, machine-readable view of the player — what a future
    'brain' module reads: per-skill rating + status + evidence, plus rolled-up
    strengths / weaknesses / improvement priorities."""
    profile = get_or_create_profile(db)
    grouped = _accepted_findings_by_aspect(db)
    skills = list_skills(db)

    skill_items: list[schemas.SkillReportItem] = []
    for s in skills:
        evidence = [t.text for t in grouped.get(s.aspect, [])][:5]
        if s.rating is None and not evidence and s.status == "neutral":
            continue  # unrated, no evidence → omit from the report
        skill_items.append(schemas.SkillReportItem(
            aspect=s.aspect, rating=s.rating, status=s.status,
            assessment=s.assessment, priority=s.priority, evidence=evidence,
        ))

    accepted = (
        db.query(VATrait)
        .filter(VATrait.status == "accepted")
        .order_by(VATrait.created_at)
        .all()
    )
    strengths = [t.text for t in accepted if t.polarity == "strength"]
    weaknesses = [t.text for t in accepted if t.polarity == "weakness"]

    # Improvement priorities: skills with an explicit priority first (lower =
    # more urgent), then the lowest-rated skills.
    rated = [s for s in skills if s.rating is not None or s.priority is not None]
    rated.sort(key=lambda s: (
        s.priority if s.priority is not None else 99,
        s.rating if s.rating is not None else 99,
    ))
    priorities = [
        f"{ _ASPECT_LABEL.get(s.aspect, s.aspect) }: {s.assessment or s.status}"
        for s in rated
        if s.status in ("weakness", "needs_work", "improving") or s.priority is not None
    ][:5]

    reviewed = db.query(VAClip).filter(VAClip.reviewed_at.isnot(None)).count()
    return schemas.ReportOut(
        name=profile.name, handed=profile.handed, grip=profile.grip,
        style=profile.style, overall_summary=profile.overall_summary,
        skills=skill_items, strengths=strengths, weaknesses=weaknesses,
        improvement_priorities=priorities,
        clips_reviewed=reviewed, findings_accepted=len(accepted),
    )


_ASPECT_LABEL = {
    "serve": "Giao bóng",
    "receive": "Đỡ giao bóng",
    "forehand": "Phải tay",
    "backhand": "Trái tay",
    "footwork": "Bộ chân",
    "stance_posture": "Tư thế",
    "tactics": "Chiến thuật",
    "mental": "Tâm lý",
    "physical": "Thể lực",
}
