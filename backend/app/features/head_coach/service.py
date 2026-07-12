"""Head Coach service: gather the specialist reports, synthesise the verdict.

The Head Coach is a *consumer*. It calls the Tier-1 specialists' own service
functions in-process (never HTTP), assembles a compact bundle, asks the local
text model for a strict holistic verdict + plan, and persists the result as a
snapshot. See HEAD_COACH_PLAN.md.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time

import httpx
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.settings import HEAD_COACH_MODEL, OLLAMA_BASE_URL
from app.features.head_coach import schemas
from app.features.head_coach.models import HeadCoachAssessment
from app.features.head_coach.prompt import RESPONSE_SCHEMA, SYSTEM_PROMPT
from app.features.playbook import service as playbook_service
from app.features.tracker import service as tracker_service
from app.features.training import service as training_service
from app.features.video_analysis import service as video_service
from app.features.video_analysis.schemas import ASPECT_LABEL_VI as _ASPECT_VI

log = logging.getLogger(__name__)

# Window used for the match / training-load stats fed to the coach.
_STATS_WINDOW_DAYS = 90


# ---------------------------------------------------------------- gather inputs
def gather_bundle(db: Session) -> schemas.SourceSummary:
    """Assemble a compact, human-readable snapshot of all four specialists."""
    today = dt.date.today()
    date_from = today - dt.timedelta(days=_STATS_WINDOW_DAYS)

    video = video_service.build_report(db)
    training = training_service.report(db)
    stats = tracker_service.build_stats(db, date_from, today)
    tactics = playbook_service.list_tactics(db)

    video_sum = {
        "player": video.name,
        "handed": video.handed,
        "grip": video.grip,
        "style": video.style,
        "overall_summary": video.overall_summary or "",
        "reports_reviewed": video.reports_reviewed,
        "findings_accepted": video.findings_accepted,
        "skills": [
            {
                "aspect": _ASPECT_VI.get(s.aspect, s.aspect),
                "setting": s.setting,
                "rating": s.rating,
                "status": s.status,
                "assessment": s.assessment or "",
                "priority": s.priority,
            }
            for s in video.skills
        ],
        "strengths": video.strengths,
        "weaknesses": video.weaknesses,
        "improvement_priorities": video.improvement_priorities,
        # Development over time: per-aspect-and-setting rating history.
        "skill_history": [
            {
                "aspect": _ASPECT_VI.get(h.aspect, h.aspect),
                "setting": h.setting,
                "points": [
                    {"date": p.analysis_date.isoformat(), "rating": p.rating, "status": p.status}
                    for p in h.points
                ],
            }
            for h in video.skill_history
        ],
        "findings_timeline": [
            {
                "date": fp.analysis_date.isoformat(),
                "aspect": _ASPECT_VI.get(fp.aspect, fp.aspect),
                "polarity": fp.polarity,
                "text": fp.text,
                "setting": fp.setting,
            }
            for fp in video.findings_timeline
        ],
        # Practice vs real-match contrast per aspect (the in-match gap).
        "practice_vs_match": [
            {
                "aspect": _ASPECT_VI.get(s.aspect, s.aspect),
                "practice": f"{s.practice_strengths}↑/{s.practice_weaknesses}↓",
                "match": f"{s.match_strengths}↑/{s.match_weaknesses}↓",
            }
            for s in video.practice_vs_match
        ],
    }

    training_sum = {
        "level": training.current_level_vi,
        "total_sessions_done": training.total_sessions_done,
        "sessions_last_7d": training.sessions_last_7d,
        "sessions_last_30d": training.sessions_last_30d,
        "days_since_last": training.days_since_last,
        "current_streak": training.current_streak,
        "intensity_bias": training.intensity_bias,
        "muscle_volume": {mv.muscle: mv.times for mv in training.muscle_volume},
        "summary": training.summary_vi,
    }

    def _ms(m) -> dict:
        return {"played": m.total, "wins": m.wins, "losses": m.losses, "win_rate": m.win_rate}

    match_sum = {
        "window_days": _STATS_WINDOW_DAYS,
        "days_trained": stats.days_trained,
        "days_physical": stats.days_physical,
        "minutes_total": stats.minutes_total,
        "minutes_by_category": {c.label: c.minutes for c in stats.minutes_by_category},
        "overall": _ms(stats.overall),
        "singles": _ms(stats.singles),
        "doubles": _ms(stats.doubles),
        "vs_pips": _ms(stats.vs_pips),
    }

    tactics_sum = {
        "count": len(tactics),
        "favorites": [t.title for t in tactics if t.is_favorite][:10],
        "titles": [t.title for t in tactics][:25],
    }

    return schemas.SourceSummary(
        video=video_sum,
        training=training_sum,
        match=match_sum,
        tactics=tactics_sum,
        generated_for_range=f"{date_from.isoformat()} → {today.isoformat()}",
    )


def _bundle_to_text(b: schemas.SourceSummary) -> str:
    """Render the bundle into the Vietnamese context block fed to the model."""
    v, t, m, tac = b.video, b.training, b.match, b.tactics
    _setting_vi = {"practice": "TẬP", "match": "ĐẤU"}

    # Skills are rated separately for practice vs match.
    skills_lines = "\n".join(
        f"  - {s['aspect']} [{_setting_vi.get(s.get('setting'), 'TẬP')}]: "
        f"{'điểm ' + str(s['rating']) + '/10' if s.get('rating') is not None else 'chưa chấm'}, "
        f"trạng thái {s['status']}"
        f"{' — ' + s['assessment'] if s.get('assessment') else ''}"
        for s in v.get("skills", [])
    ) or "  (chưa có dữ liệu kỹ năng)"

    strengths = "; ".join(v.get("strengths", [])) or "(chưa ghi nhận)"
    weaknesses = "; ".join(v.get("weaknesses", [])) or "(chưa ghi nhận)"

    # Development over time: for each (aspect, setting) with ≥2 dated rating
    # points, show the first→latest movement (progress vs stagnation).
    prog_lines = []
    for h in v.get("skill_history", []):
        pts = h.get("points", [])
        if len(pts) >= 2 and pts[0].get("rating") is not None and pts[-1].get("rating") is not None:
            first, last = pts[0], pts[-1]
            arrow = "↑" if last["rating"] > first["rating"] else (
                "↓" if last["rating"] < first["rating"] else "→")
            prog_lines.append(
                f"  - {h['aspect']} [{_setting_vi.get(h.get('setting'), 'TẬP')}]: "
                f"{first['rating']}/10 ({first['date']}) "
                f"{arrow} {last['rating']}/10 ({last['date']})"
            )
    trends = ("\n" + "\n".join(prog_lines)) if prog_lines else " (chưa đủ dữ liệu nhiều mốc)"

    # The most recent dated findings (last 8) — what the latest analyses said,
    # tagged with TẬP (practice) / ĐẤU (match).
    timeline = v.get("findings_timeline", [])
    recent_lines = "; ".join(
        f"{fp['date']} ({_setting_vi.get(fp.get('setting'), 'TẬP')}) [{fp['aspect']}] {fp['text']}"
        for fp in timeline[-8:]
    ) or "(chưa có)"

    # Practice-vs-match gap (↑ = nhận xét tốt, ↓ = nhận xét yếu).
    pvm = v.get("practice_vs_match", [])
    pvm_lines = "\n".join(
        f"  - {s['aspect']}: khi TẬP {s['practice']} · khi ĐẤU {s['match']}" for s in pvm
    ) or "  (chưa đủ dữ liệu để so sánh)"

    def _wr(d: dict) -> str:
        wr = d.get("win_rate")
        wr_s = f"{round(wr * 100)}%" if wr is not None else "—"
        return f"{d['played']} trận (T{d['wins']}/B{d['losses']}, thắng {wr_s})"

    minutes_cat = "; ".join(f"{k}: {v_}p" for k, v_ in m.get("minutes_by_category", {}).items()) or "—"
    muscle = "; ".join(f"{k}×{v_}" for k, v_ in t.get("muscle_volume", {}).items()) or "—"

    return (
        f"=== HỒ SƠ KỸ THUẬT (từ phân tích kỹ thuật, đã duyệt {v.get('findings_accepted', 0)} "
        f"nhận xét / {v.get('reports_reviewed', 0)} bản phân tích) ===\n"
        f"Vận động viên: {v.get('player')} — thuận tay {v.get('handed')}, vợt {v.get('grip')}, "
        f"lối đánh {v.get('style') or 'chưa rõ'}.\n"
        f"Tóm tắt hiện có: {v.get('overall_summary') or '(chưa có)'}\n"
        f"Kỹ năng theo mảng:\n{skills_lines}\n"
        f"Điểm mạnh: {strengths}\nĐiểm yếu: {weaknesses}\n"
        f"Tiến độ kỹ năng theo thời gian (điểm đầu → điểm gần nhất):{trends}\n"
        f"CHÊNH LỆCH TẬP vs ĐẤU theo mảng:\n{pvm_lines}\n"
        f"Nhận xét gần đây (theo ngày): {recent_lines}\n\n"
        f"=== THỂ LỰC (Training Center) ===\n"
        f"Cấp độ: {t.get('level')}; tổng buổi đã xong: {t.get('total_sessions_done')}; "
        f"7 ngày: {t.get('sessions_last_7d')} buổi; 30 ngày: {t.get('sessions_last_30d')} buổi; "
        f"chuỗi hiện tại: {t.get('current_streak')} ngày; "
        f"số ngày từ buổi gần nhất: {t.get('days_since_last')}; "
        f"điều chỉnh cường độ: {t.get('intensity_bias')}.\n"
        f"Khối lượng theo nhóm cơ: {muscle}\n"
        f"Tự nhận xét tuần: {t.get('summary')}\n\n"
        f"=== TẬP & THI ĐẤU ({m.get('window_days')} ngày gần nhất) ===\n"
        f"Số ngày tập: {m.get('days_trained')}; ngày thể lực: {m.get('days_physical')}; "
        f"tổng thời lượng: {m.get('minutes_total')} phút ({minutes_cat}).\n"
        f"Đơn: {_wr(m.get('singles', {}))}\n"
        f"Đôi: {_wr(m.get('doubles', {}))}\n"
        f"Gặp đối thủ gai: {_wr(m.get('vs_pips', {}))}\n"
        f"Tổng các trận: {_wr(m.get('overall', {}))}\n\n"
        f"=== SỔ TAY CHIẾN THUẬT ===\n"
        f"Đang lưu {tac.get('count')} chiến thuật"
        f"{'; tâm đắc: ' + ', '.join(tac.get('favorites', [])) if tac.get('favorites') else ''}.\n"
    )


# ---------------------------------------------------------------- synthesise
def _call_model(context_text: str, player_name: str) -> dict:
    user_text = (
        f"Dưới đây là TOÀN BỘ số liệu hiện có về học trò {player_name}. Hãy đọc kỹ, "
        "đánh giá NGHIÊM KHẮC dựa trên số liệu, rồi đưa ra kết luận + kế hoạch.\n\n"
        f"{context_text}\n"
        "Yêu cầu trả về (tiếng Việt, đúng JSON schema):\n"
        "- overall_assessment: 3-5 câu, nêu vấn đề trước, trích số liệu cụ thể.\n"
        "- top_priorities: 3-5 ưu tiên xếp theo mức cấp thiết (kèm 'why' và 'source').\n"
        "- directives: mệnh lệnh TĂNG CƯỜNG đo được (area ∈ training/playing_hours/"
        "matches/skill/tactics/recovery; kèm target số cụ thể và reason từ số liệu).\n"
        "- tactics: 2-4 đề xuất chiến thuật áp dụng trong trận (situation → action).\n"
        "- week_plan: kế hoạch 1 tuần, mỗi ngày có focus + detail (gắn với tập thể lực "
        "và bài sửa điểm yếu; nhớ giới hạn an toàn đầu gối).\n"
        "- watch_items: cảnh báo (dữ liệu mỏng/cũ, an toàn, điều cần theo dõi)."
    )
    payload = {
        "model": HEAD_COACH_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": {"temperature": 0.3, "num_ctx": 16384},
    }
    t0 = time.monotonic()
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=600.0)
    resp.raise_for_status()
    log.info("head coach: model=%s took=%.1fs", HEAD_COACH_MODEL, time.monotonic() - t0)
    content = resp.json().get("message", {}).get("content", "{}")
    return json.loads(content) if content else {}


def start_generate(db: Session) -> schemas.AssessmentOut:
    """Create a `generating` placeholder row; the heavy work (gather + local
    LLM, up to minutes) runs in run_generate_job on a background task. Mirrors
    the video-analysis parse flow: the UI polls /assessment until the status
    leaves `generating`."""
    row = HeadCoachAssessment(model=HEAD_COACH_MODEL, status="generating")
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def run_generate_job(assessment_id: int) -> None:
    """Background job: gather the bundle, call the model, fill the snapshot."""
    db = SessionLocal()
    try:
        row = db.get(HeadCoachAssessment, assessment_id)
        if row is None or row.status != "generating":
            return
        try:
            bundle = gather_bundle(db)
            data = _call_model(
                _bundle_to_text(bundle),
                player_name=bundle.video.get("player") or "vận động viên",
            )
        except Exception as exc:  # noqa: BLE001 — surfaced to the GUI via status
            log.exception("head coach generate(%d) failed", assessment_id)
            db.rollback()
            row = db.get(HeadCoachAssessment, assessment_id)
            if row is not None:
                row.status = "error"
                row.error_msg = str(exc)[:1000]
                db.commit()
            return
        row.overall_assessment = data.get("overall_assessment", "")
        row.top_priorities_json = json.dumps(data.get("top_priorities", []), ensure_ascii=False)
        row.directives_json = json.dumps(data.get("directives", []), ensure_ascii=False)
        row.tactics_json = json.dumps(data.get("tactics", []), ensure_ascii=False)
        row.week_plan_json = json.dumps(data.get("week_plan", []), ensure_ascii=False)
        row.watch_items_json = json.dumps(data.get("watch_items", []), ensure_ascii=False)
        row.sources_json = bundle.model_dump_json()
        row.status = "done"
        row.error_msg = None
        db.commit()
    finally:
        db.close()


def generate(db: Session) -> schemas.AssessmentOut:
    """Synchronous gather → synthesise → persist (used by scripts/tests; the
    HTTP API uses start_generate + run_generate_job instead)."""
    out = start_generate(db)
    run_generate_job(out.id)
    row = db.get(HeadCoachAssessment, out.id)
    db.refresh(row)
    return _to_out(row)


def _to_out(row: HeadCoachAssessment) -> schemas.AssessmentOut:
    return schemas.AssessmentOut(
        id=row.id,
        created_at=row.created_at,
        model=row.model,
        status=row.status or "done",
        error_msg=row.error_msg,
        overall_assessment=row.overall_assessment,
        top_priorities=[schemas.Priority(**p) for p in json.loads(row.top_priorities_json)],
        directives=[schemas.Directive(**d) for d in json.loads(row.directives_json)],
        tactics=[schemas.TacticSuggestion(**t) for t in json.loads(row.tactics_json)],
        week_plan=[schemas.PlanDay(**d) for d in json.loads(row.week_plan_json)],
        watch_items=json.loads(row.watch_items_json),
        sources=schemas.SourceSummary(**json.loads(row.sources_json)),
    )


def get_latest(db: Session) -> schemas.AssessmentOut:
    """The most recent *completed* verdict, or an `empty` placeholder if none
    generated yet (in-flight/error rows are reported via get_status)."""
    row = (
        db.query(HeadCoachAssessment)
        .filter(HeadCoachAssessment.status == "done")
        .order_by(HeadCoachAssessment.created_at.desc())
        .first()
    )
    if row is None:
        return schemas.AssessmentOut(empty=True)
    return _to_out(row)


def get_status(db: Session) -> schemas.GenerateStatusOut:
    """The most recent generation attempt's state — what the UI polls."""
    row = (
        db.query(HeadCoachAssessment)
        .order_by(HeadCoachAssessment.created_at.desc())
        .first()
    )
    if row is None:
        return schemas.GenerateStatusOut(status="none")
    return schemas.GenerateStatusOut(
        id=row.id, status=row.status or "done", error_msg=row.error_msg
    )


def live_sources(db: Session) -> schemas.SourcesOut:
    """The current bundle without calling the AI — transparency / debug view."""
    return schemas.SourcesOut(sources=gather_bundle(db))
