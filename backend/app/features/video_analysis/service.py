"""Business logic for the Technique Analysis tab.

The tab no longer processes video. The user pastes an analysis produced
elsewhere (e.g. a cloud model), tagged with the date it pertains to; the local
text model parses it into proposed findings; the user reviews them; accepted
findings feed the skill ledger + profile summaries and a dated skill-history
series, all read by the Head Coach to track development over time.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.settings import TEXT_MODEL
from app.features.video_analysis import schemas, text_synth
from app.features.video_analysis.models import (
    VAProfile,
    VAReport,
    VASkill,
    VASkillSnapshot,
    VATrait,
    _utcnow,
)


log = logging.getLogger(__name__)

# Prompt-size caps: the local model's context is finite and Ollama silently
# truncates overlong prompts — cap what we feed it, keeping the MOST RECENT.
_PROFILE_TRAIT_CAP = 150       # traits fed into the profile summary
_SKILL_FINDINGS_PER_ASPECT = 20  # findings per (setting, aspect) for the ledger


def _basics(profile: VAProfile) -> dict:
    """Profile facts shared by every prompt (name is the editable profile name)."""
    return {
        "name": profile.name,
        "handed": profile.handed,
        "grip": profile.grip,
        "style": profile.style,
    }


def _clamp01(v: object) -> float | None:
    try:
        return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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
    """Fold accepted findings into the profile summary fields via the LLM.

    Capped to the most recent _PROFILE_TRAIT_CAP traits (chronological order
    preserved) so the prompt never outgrows the model's context window."""
    profile = get_or_create_profile(db)
    recent = (
        db.query(VATrait)
        .filter(VATrait.status == "accepted")
        .filter(VATrait.polarity.in_(["strength", "weakness"]))  # skip "Chưa quan sát"
        .order_by(VATrait.created_at.desc())
        .limit(_PROFILE_TRAIT_CAP)
        .all()
    )
    traits = [
        {"aspect": t.aspect, "polarity": t.polarity, "text": t.text}
        for t in reversed(recent)  # oldest → newest, like before
    ]
    result = text_synth.synthesize_profile(_basics(profile), traits)
    for field in (
        "serve_summary", "footwork_summary", "posture_summary",
        "strengths_summary", "weaknesses_summary", "overall_summary",
    ):
        if field in result:
            setattr(profile, field, result[field])
    db.commit()
    db.refresh(profile)
    return profile


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
        source_report_id=None,  # manual entry
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


# ------------------------------------------------------------------ reports
def list_reports(db: Session) -> list[VAReport]:
    """Newest analysis first (by the date it pertains to, then by creation)."""
    return (
        db.query(VAReport)
        .order_by(VAReport.analysis_date.desc(), VAReport.created_at.desc())
        .all()
    )


def get_report(db: Session, report_id: int) -> VAReport | None:
    return db.get(VAReport, report_id)


def _clamp_date(d: dt.date | None) -> dt.date:
    """Default to today; never accept a future date (clamp to today)."""
    today = dt.date.today()
    return d if (d is not None and d <= today) else today


def create_report(db: Session, payload: schemas.ReportCreateIn) -> VAReport:
    """Persist a pasted analysis and queue parsing. Status starts 'parsing'."""
    text = (payload.source_text or "").strip()
    if not text:
        raise ValueError("Chưa có nội dung phân tích để lưu.")
    when = _clamp_date(payload.analysis_date)
    setting = payload.setting if payload.setting in schemas.SETTINGS else "practice"
    report = VAReport(
        analysis_date=when,
        setting=setting,
        title=(payload.title or "").strip() or f"Phân tích {when.isoformat()}",
        context=(payload.context or "").strip(),
        source_text=text,
        model=TEXT_MODEL,
        status="parsing",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def parse_report(report_id: int) -> None:
    """Background job: parse the report's text into proposed findings."""
    db = SessionLocal()
    try:
        report = db.get(VAReport, report_id)
        if report is None or report.status != "parsing":
            return
        profile = get_or_create_profile(db)
        try:
            findings = text_synth.extract_findings(
                report.source_text, _basics(profile), report.context
            )
        except Exception as exc:  # noqa: BLE001 — surface to the GUI
            log.exception("parse_report(%d): extract_findings failed", report_id)
            report.status = "error"
            report.error_msg = str(exc)[:1000]
            db.commit()
            return

        # The pasted analysis was already curated by the user before copying it
        # in, so parsed findings are auto-accepted (no review gate). The user can
        # still edit/remove individual findings afterwards.
        # Replace any prior findings for this report (re-parse is idempotent).
        db.query(VATrait).filter(VATrait.source_report_id == report_id).delete()
        now = _utcnow()
        for f in findings:
            db.add(VATrait(
                aspect=f["aspect"],
                polarity=f["polarity"],
                text=f["text"],
                ai_text=f["text"],
                confidence=_clamp01(f.get("confidence")),
                status="accepted",
                reviewed_at=now,
                source_report_id=report_id,
            ))
        report.error_msg = None
        report.reviewed_at = now
        db.commit()  # findings persisted (status still 'parsing' → UI keeps polling)

        # Auto-rebuild the skill ledger (per setting) from all accepted findings,
        # so progress updates without a manual "Cập nhật hồ sơ kỹ năng" click. A
        # model/Ollama failure here is non-fatal: the findings are already saved
        # and the user can rebuild manually later.
        try:
            regenerate_skills(db)
        except Exception:  # noqa: BLE001
            log.exception(
                "parse_report(%d): auto regenerate_skills failed — findings are "
                "saved; rebuild the ledger manually from the GUI", report_id,
            )
            db.rollback()

        report.status = "reviewed"
        db.commit()
    finally:
        db.close()


def delete_report(db: Session, report_id: int) -> bool:
    """Delete a report and its findings (cascade)."""
    report = db.get(VAReport, report_id)
    if report is None:
        return False
    db.delete(report)
    db.commit()
    return True


def report_detail_out(report: VAReport) -> schemas.AnalysisReportDetailOut:
    base = schemas.AnalysisReportOut.model_validate(report)
    return schemas.AnalysisReportDetailOut(
        **base.model_dump(),
        traits=[
            schemas.TraitOut.model_validate(t)
            for t in sorted(report.traits, key=lambda t: (t.polarity, t.id))
        ],
    )


def review_report(db: Session, report_id: int, payload: schemas.ReviewIn) -> VAReport | None:
    """Apply the user's accept/reject (and edits) to a report's findings, then
    mark the report reviewed. Only accepted findings count towards the profile."""
    report = db.get(VAReport, report_id)
    if report is None:
        return None
    by_id = {t.id: t for t in report.traits}
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
    report.reviewed_at = now
    report.status = "reviewed"
    db.commit()
    db.refresh(report)
    return report


# ------------------------------------------------------------- skill ledger
def list_skills(db: Session) -> list[VASkill]:
    """The skill ledger, ordered by aspect then setting (practice before match).
    Two rows per aspect — a separate rating for practice and for match."""
    a_order = {a: i for i, a in enumerate(schemas.SKILL_ASPECTS)}
    s_order = {s: i for i, s in enumerate(schemas.SETTINGS)}
    skills = db.query(VASkill).all()
    return sorted(
        skills,
        key=lambda s: (a_order.get(s.aspect, 99), s_order.get(s.setting, 99)),
    )


def update_skill(
    db: Session, aspect: str, setting: str, payload: schemas.SkillIn
) -> VASkill | None:
    skill = (
        db.query(VASkill)
        .filter(VASkill.aspect == aspect, VASkill.setting == setting)
        .first()
    )
    if skill is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    db.commit()
    db.refresh(skill)
    return skill


def _accepted_by_setting_aspect(db: Session) -> dict[tuple[str, str], list[VATrait]]:
    """Accepted strength/weakness findings grouped by (setting, aspect). "Chưa
    quan sát" (neutral) findings + 'other' carry no rating signal → excluded."""
    grouped: dict[tuple[str, str], list[VATrait]] = {}
    for t, _when, setting in _accepted_findings_with_setting(db):
        if t.aspect not in schemas.SKILL_ASPECTS:
            continue
        grouped.setdefault((setting, t.aspect), []).append(t)
    return grouped


def _latest_analysis_date(db: Session) -> dt.date:
    """The most recent report's date (the date to stamp a new skill snapshot),
    or today if there are no reports yet."""
    row = db.query(VAReport.analysis_date).order_by(VAReport.analysis_date.desc()).first()
    return row[0] if row else dt.date.today()


def _record_skill_snapshots(db: Session, when: dt.date) -> None:
    """Upsert one dated point per (aspect, setting) for ``when`` → the
    rating-over-time series, tracked separately for practice and match. Only
    skills with a rating or a non-neutral status are worth a point."""
    existing = {
        (s.aspect, s.setting): s
        for s in db.query(VASkillSnapshot).filter(VASkillSnapshot.analysis_date == when).all()
    }
    report = db.query(VAReport).filter(VAReport.analysis_date == when).order_by(
        VAReport.created_at.desc()
    ).first()
    report_id = report.id if report else None
    for skill in db.query(VASkill).all():
        if skill.rating is None and skill.status == "neutral":
            continue
        snap = existing.get((skill.aspect, skill.setting))
        if snap is None:
            db.add(VASkillSnapshot(
                analysis_date=when, aspect=skill.aspect, setting=skill.setting,
                rating=skill.rating, status=skill.status, report_id=report_id,
            ))
        else:
            snap.rating = skill.rating
            snap.status = skill.status
            snap.report_id = report_id


def regenerate_skills(db: Session) -> list[VASkill]:
    """Synthesise the skill ledger from accepted findings via the local LLM,
    SEPARATELY for practice and match (one synthesis call per setting), then
    record dated snapshots so each setting's progress is trackable over time."""
    profile = get_or_create_profile(db)
    by_sa = _accepted_by_setting_aspect(db)
    skills_map = {(s.aspect, s.setting): s for s in db.query(VASkill).all()}
    now = _utcnow()

    for setting in schemas.SETTINGS:
        # Cap to the most recent findings per aspect (items are oldest-first)
        # so the prompt stays inside the model's context window.
        findings_by_aspect = {
            aspect: [
                {"polarity": t.polarity, "text": t.text}
                for t in items[-_SKILL_FINDINGS_PER_ASPECT:]
            ]
            for (st, aspect), items in by_sa.items()
            if st == setting
        }
        if not findings_by_aspect:
            continue  # no findings in this setting → leave its rows untouched
        results = text_synth.synthesize_skills(
            _basics(profile), findings_by_aspect, setting=setting
        )
        for item in results:
            aspect = item.get("aspect")
            skill = skills_map.get((aspect, setting))
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

    db.flush()  # ledger updated → snapshot reads the fresh values
    _record_skill_snapshots(db, _latest_analysis_date(db))
    db.commit()
    return list_skills(db)


# ---------------------------------------------------- progress over time
def skill_history(db: Session) -> list[schemas.SkillHistory]:
    """Per (aspect, setting) dated rating points, ordered by date — the
    development series, tracked separately for practice and match."""
    rows = (
        db.query(VASkillSnapshot)
        .order_by(VASkillSnapshot.aspect, VASkillSnapshot.analysis_date)
        .all()
    )
    by_key: dict[tuple[str, str], list[schemas.SkillPoint]] = {}
    for r in rows:
        by_key.setdefault((r.aspect, r.setting), []).append(
            schemas.SkillPoint(analysis_date=r.analysis_date, rating=r.rating, status=r.status)
        )
    a_order = {a: i for i, a in enumerate(schemas.SKILL_ASPECTS)}
    s_order = {s: i for i, s in enumerate(schemas.SETTINGS)}
    return [
        schemas.SkillHistory(aspect=a, setting=st, points=pts)
        for (a, st), pts in sorted(
            by_key.items(), key=lambda kv: (a_order.get(kv[0][0], 99), s_order.get(kv[0][1], 99))
        )
    ]


def _accepted_findings_with_setting(db: Session) -> list[tuple[VATrait, object, str]]:
    """Accepted strength/weakness findings joined with their report's date +
    setting, oldest first."""
    return (
        db.query(VATrait, VAReport.analysis_date, VAReport.setting)
        .join(VAReport, VATrait.source_report_id == VAReport.id)
        .filter(VATrait.status == "accepted")
        .filter(VATrait.polarity.in_(["strength", "weakness"]))
        .order_by(VAReport.analysis_date, VATrait.created_at)
        .all()
    )


def findings_timeline(db: Session) -> list[schemas.FindingPoint]:
    """All accepted strength/weakness findings, dated + setting-tagged, oldest
    first — so the Head Coach can read how the technique evolved."""
    return [
        schemas.FindingPoint(
            analysis_date=when, aspect=t.aspect, polarity=t.polarity,
            text=t.text, setting=setting,
        )
        for t, when, setting in _accepted_findings_with_setting(db)
    ]


def practice_vs_match(db: Session) -> list[schemas.AspectSettingStat]:
    """Per-aspect contrast of practice vs real-match findings. Surfaces the gap
    the player flagged: technique that holds up in training but breaks down in
    matches. Only aspects with at least one finding are included."""
    by_aspect: dict[str, schemas.AspectSettingStat] = {}
    for t, _when, setting in _accepted_findings_with_setting(db):
        stat = by_aspect.get(t.aspect)
        if stat is None:
            stat = schemas.AspectSettingStat(aspect=t.aspect)
            by_aspect[t.aspect] = stat
        is_match = setting == "match"
        if t.polarity == "strength":
            if is_match:
                stat.match_strengths += 1
            else:
                stat.practice_strengths += 1
        else:  # weakness
            if is_match:
                stat.match_weaknesses += 1
            else:
                stat.practice_weaknesses += 1
        samples = stat.match_samples if is_match else stat.practice_samples
        if len(samples) < 4:
            samples.append(f"[{t.polarity}] {t.text}")
    order = {a: i for i, a in enumerate(schemas.SKILL_ASPECTS)}
    return sorted(by_aspect.values(), key=lambda s: order.get(s.aspect, 99))


# --------------------------------------------------- structured player report
def build_report(db: Session) -> schemas.ReportOut:
    """The systematic, machine-readable view of the player the Head Coach reads:
    per-skill rating + status + evidence, rolled-up strengths/weaknesses/
    priorities, plus the development-over-time series."""
    profile = get_or_create_profile(db)
    by_sa = _accepted_by_setting_aspect(db)
    skills = list_skills(db)

    skill_items: list[schemas.SkillReportItem] = []
    for s in skills:
        evidence = [t.text for t in by_sa.get((s.setting, s.aspect), [])][:5]
        if s.rating is None and not evidence and s.status == "neutral":
            continue  # unrated, no evidence → omit from the report
        skill_items.append(schemas.SkillReportItem(
            aspect=s.aspect, setting=s.setting, rating=s.rating, status=s.status,
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
    # more urgent), then the lowest-rated skills. Setting-tagged so a match
    # weakness reads distinctly from a practice one.
    rated = [s for s in skills if s.rating is not None or s.priority is not None]
    rated.sort(key=lambda s: (
        s.priority if s.priority is not None else 99,
        s.rating if s.rating is not None else 99,
    ))
    priorities = [
        f"{ _ASPECT_LABEL.get(s.aspect, s.aspect) } "
        f"[{_SETTING_LABEL.get(s.setting, s.setting)}]: {s.assessment or s.status}"
        for s in rated
        if s.status in ("weakness", "needs_work", "improving") or s.priority is not None
    ][:5]

    reviewed = db.query(VAReport).filter(VAReport.reviewed_at.isnot(None)).count()
    return schemas.ReportOut(
        name=profile.name, handed=profile.handed, grip=profile.grip,
        style=profile.style, overall_summary=profile.overall_summary,
        skills=skill_items, strengths=strengths, weaknesses=weaknesses,
        improvement_priorities=priorities,
        skill_history=skill_history(db),
        findings_timeline=findings_timeline(db),
        practice_vs_match=practice_vs_match(db),
        reports_reviewed=reviewed, findings_accepted=len(accepted),
    )


_ASPECT_LABEL = schemas.ASPECT_LABEL_VI
_SETTING_LABEL = schemas.SETTING_LABEL_VI
