"""Head Coach service: gather database facts, synthesise the verdict.

The Head Coach is a *consumer*. It calls the tracker/training service
functions in-process (never HTTP), assembles a compact facts bundle (volume,
racket time, per-match results with opponent context, physical load, day
notes), asks the local text model for a strict holistic verdict + plan, and
persists the result as a snapshot. See HEAD_COACH_PLAN.md.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time

import httpx
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.settings import HEAD_COACH_MODEL, OLLAMA_BASE_URL, TEXT_MODEL
from app.features.head_coach import schemas
from app.features.head_coach.models import HeadCoachAssessment
from app.features.head_coach.prompt import RESPONSE_SCHEMA, SYSTEM_PROMPT
from app.features.tracker import service as tracker_service
from app.features.tracker.models import DayNote
from app.features.training import service as training_service
from app.features.training.models import TrainingSession
# Only for the player's (editable) profile name — not for analysis data.
from app.features.video_analysis.service import get_or_create_profile

log = logging.getLogger(__name__)

# Window used for the volume / training-load stats fed to the coach.
_STATS_WINDOW_DAYS = 90
# Window for the detailed match analytics (head-to-head, level splits, trend).
# build_match_stats additionally clamps to its own data floor.
_MATCH_DETAIL_DAYS = 180
# How many recent day notes the coach reads (the player's own observations).
_RECENT_NOTES = 12
# Below this many matches a segment is tagged [MẪU NHỎ] in the context block
# and the prompt forbids drawing win-rate conclusions from it.
MIN_SAMPLE_MATCHES = 5

_LEVEL_VI = {"below": "dưới cơ", "equal": "ngang cơ", "above": "trên cơ"}


# ---------------------------------------------------------------- gather inputs
def _ms(m) -> dict:
    return {"played": m.total, "wins": m.wins, "losses": m.losses, "win_rate": m.win_rate}


def gather_bundle(db: Session) -> schemas.SourceSummary:
    """Assemble the coach's inputs — hard facts from the database ONLY.

    Sources: the Daily Tracker (per-day volume + every match with its score,
    opponent level, pips, practice/official) and the Training Center (physical
    load, adherence, pain). No AI-derived skill ratings: the retired technique-
    analysis pipeline produced model guesses, not observations."""
    today = dt.date.today()
    date_from = today - dt.timedelta(days=_STATS_WINDOW_DAYS)
    detail_from = today - dt.timedelta(days=_MATCH_DETAIL_DAYS)

    profile = get_or_create_profile(db)
    training = training_service.report(db)
    stats = tracker_service.build_stats(db, date_from, today)
    # Detailed match analytics (named-opponent matches; clamped to its floor).
    detail = tracker_service.build_match_stats(db, detail_from, today, "all", "all", "month")
    practice = tracker_service.build_match_stats(db, detail_from, today, "all", "practice", "month")
    official = tracker_service.build_match_stats(db, detail_from, today, "all", "official", "month")

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

    match_sum = {
        "window_days": _STATS_WINDOW_DAYS,
        "days_trained": stats.days_trained,
        "days_physical": stats.days_physical,
        "minutes_total": stats.minutes_total,
        "minutes_by_category": {c.label: c.minutes for c in stats.minutes_by_category},
        "racket_minutes_total": stats.racket_minutes_total,
        "racket_minutes_training": stats.racket_minutes_training,
        "racket_minutes_matches": stats.racket_minutes_matches,
        "overall": _ms(stats.overall),
        "singles": _ms(stats.singles),
        "doubles": _ms(stats.doubles),
        "vs_pips": _ms(stats.vs_pips),
    }

    # Head-to-head: the most-played singles opponents (problem opponents float
    # up via win_rate), plus level splits, practice-vs-official and the trend.
    top_h2h = sorted(detail.singles_h2h, key=lambda r: -r.played)[:8]
    match_detail = {
        "window": f"{detail.date_from.isoformat()} → {detail.date_to.isoformat()}",
        "by_level": {
            r.level: _ms(r.stats) for r in detail.by_level
        },
        "practice": _ms(practice.overall),
        "official": _ms(official.overall),
        "trend_by_month": [
            {
                "label": b.label,
                "played": b.matches,
                "wins": b.wins,
                "losses": b.losses,
                "win_rate": b.win_rate,
            }
            for b in detail.trend
        ],
        "top_h2h": [
            {
                "name": r.name,
                "level": r.level,
                "played": r.played,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "last": f"{r.last_result or ''} {r.last_date.isoformat() if r.last_date else ''}".strip(),
            }
            for r in top_h2h
        ],
    }

    # The player's own day notes — human observations, newest first.
    notes = [
        {"date": n.date.isoformat(), "text": n.text}
        for n in db.query(DayNote).order_by(DayNote.date.desc()).limit(_RECENT_NOTES).all()
    ]

    return schemas.SourceSummary(
        player=profile.name,
        training=training_sum,
        match=match_sum,
        match_detail=match_detail,
        notes=notes,
        generated_for_range=f"{date_from.isoformat()} → {today.isoformat()}",
    )


def _wr(d: dict) -> str:
    wr = d.get("win_rate")
    wr_s = f"{round(wr * 100)}%" if wr is not None else "—"
    played = d.get("played", 0)
    line = f"{played} trận (T{d.get('wins', 0)}/B{d.get('losses', 0)}, thắng {wr_s})"
    # Small samples are labelled so the model is barred from concluding on them.
    if 0 < played < MIN_SAMPLE_MATCHES:
        line += " [MẪU NHỎ]"
    return line


def _bundle_to_text(b: schemas.SourceSummary) -> str:
    """Render the bundle into the Vietnamese context block fed to the model.
    Every number here is computed by code from the database — the model only
    has to reason over the facts, never derive them."""
    t, m, d = b.training, b.match, b.match_detail

    minutes_cat = "; ".join(f"{k}: {v_}p" for k, v_ in m.get("minutes_by_category", {}).items()) or "—"
    muscle = "; ".join(f"{k}×{v_}" for k, v_ in t.get("muscle_volume", {}).items()) or "—"

    by_level = d.get("by_level", {})
    level_lines = "\n".join(
        f"  - Đối thủ {_LEVEL_VI.get(lv, lv)}: {_wr(by_level[lv])}"
        for lv in ("below", "equal", "above")
        if lv in by_level
    ) or "  (chưa có trận có tên đối thủ)"

    trend_lines = "\n".join(
        f"  - {tb['label']}: {_wr(tb)}"
        for tb in d.get("trend_by_month", [])
        if tb.get("played")
    ) or "  (chưa đủ dữ liệu)"

    # Head-to-head records are per-person facts (naturally few matches) — no
    # small-sample label here; the rule targets win-rate SEGMENTS.
    h2h_lines = "\n".join(
        f"  - {r['name']} ({_LEVEL_VI.get(r['level'], r['level'])}): "
        f"{r.get('played', 0)} trận (T{r.get('wins', 0)}/B{r.get('losses', 0)})"
        f"{'; gần nhất: ' + r['last'] if r.get('last') else ''}"
        for r in d.get("top_h2h", [])
    ) or "  (chưa có)"

    note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.notes
    ) or "  (không có ghi chú)"

    racket_total = m.get("racket_minutes_total", 0)
    racket_tr = m.get("racket_minutes_training", 0)
    racket_ma = m.get("racket_minutes_matches", 0)

    return (
        f"Vận động viên: {b.player}.\n\n"
        f"=== KHỐI LƯỢNG TẬP & CẦM VỢT ({m.get('window_days')} ngày gần nhất) ===\n"
        f"Số ngày có hoạt động: {m.get('days_trained')}; ngày thể lực: {m.get('days_physical')}.\n"
        f"Giờ tập có chủ đích: {m.get('minutes_total')} phút ({minutes_cat}).\n"
        f"TỔNG THỜI GIAN CẦM VỢT: {racket_total} phút "
        f"(tập {racket_tr}p + thi đấu ~{racket_ma}p ước từ số set).\n\n"
        f"=== KẾT QUẢ THI ĐẤU ({m.get('window_days')} ngày gần nhất) ===\n"
        f"Đơn: {_wr(m.get('singles', {}))}\n"
        f"Đôi: {_wr(m.get('doubles', {}))}\n"
        f"Gặp đối thủ đánh gai: {_wr(m.get('vs_pips', {}))}\n"
        f"Tổng các trận: {_wr(m.get('overall', {}))}\n\n"
        f"=== PHÂN TÍCH TRẬN SÂU (cửa sổ {d.get('window')}, trận có tên đối thủ) ===\n"
        f"Theo hạng đối thủ (so với học trò):\n{level_lines}\n"
        f"TRẬN TẬP vs TRẬN GIẢI: khi TẬP {_wr(d.get('practice', {}))} · "
        f"khi ĐẤU GIẢI {_wr(d.get('official', {}))}\n"
        f"Xu hướng theo tháng:\n{trend_lines}\n"
        f"Đối đầu nhiều nhất (head-to-head, đơn):\n{h2h_lines}\n\n"
        f"=== THỂ LỰC (Training Center) ===\n"
        f"Cấp độ: {t.get('level')}; tổng buổi đã xong: {t.get('total_sessions_done')}; "
        f"7 ngày: {t.get('sessions_last_7d')} buổi; 30 ngày: {t.get('sessions_last_30d')} buổi; "
        f"chuỗi hiện tại: {t.get('current_streak')} ngày; "
        f"số ngày từ buổi gần nhất: {t.get('days_since_last')}; "
        f"điều chỉnh cường độ: {t.get('intensity_bias')}.\n"
        f"Khối lượng theo nhóm cơ: {muscle}\n"
        f"Tự nhận xét tuần: {t.get('summary')}\n\n"
        f"=== GHI CHÚ HẰNG NGÀY CỦA HỌC TRÒ (mới nhất trước) ===\n"
        f"{note_lines}\n"
    )


# ---------------------------------------------------------------- synthesise
def resolve_model() -> str:
    """HEAD_COACH_MODEL when it's actually pulled in Ollama; else fall back to
    the shared TEXT_MODEL (logged). If the probe itself fails, return the
    configured model and let the chat call surface the real error."""
    if HEAD_COACH_MODEL == TEXT_MODEL:
        return HEAD_COACH_MODEL
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        names = {m["name"] for m in resp.json().get("models", [])}
    except Exception:  # noqa: BLE001 — probe failure ≠ model missing
        return HEAD_COACH_MODEL
    if HEAD_COACH_MODEL in names or f"{HEAD_COACH_MODEL}:latest" in names:
        return HEAD_COACH_MODEL
    log.warning(
        "head coach model %r is not pulled in Ollama; falling back to %r "
        "(run: ollama pull %s)", HEAD_COACH_MODEL, TEXT_MODEL, HEAD_COACH_MODEL,
    )
    return TEXT_MODEL


def _call_model(context_text: str, player_name: str, model: str | None = None) -> dict:
    user_text = (
        f"Dưới đây là TOÀN BỘ số liệu hiện có về học trò {player_name}. Hãy đọc kỹ, "
        "đánh giá NGHIÊM KHẮC dựa trên số liệu, rồi đưa ra kết luận + kế hoạch.\n\n"
        f"{context_text}\n"
        "Yêu cầu trả về (tiếng Việt, đúng JSON schema):\n"
        "- overall_assessment: 3-5 câu, nêu vấn đề trước, trích số liệu cụ thể.\n"
        "- top_priorities: 3-5 ưu tiên xếp theo mức cấp thiết (kèm 'why' và 'source').\n"
        "- directives: mệnh lệnh TĂNG CƯỜNG đo được (area ∈ training/playing_hours/"
        "matches/skill/recovery). 'order' PHẢI là một câu mệnh lệnh tiếng Việt "
        "hoàn chỉnh (ví dụ: 'Đánh ít nhất 5 trận đơn mỗi tuần với người ngang cơ "
        "trở lên') — KHÔNG được điền tên metric vào 'order'. Kèm reason từ số "
        "liệu. Nếu mệnh lệnh quy được về CHỈ TIÊU TUẦN thì điền metric (một "
        "trong: physical_sessions_per_week, racket_hours_per_week, "
        "coach_hours_per_week, matches_per_week, singles_matches_per_week, "
        "doubles_matches_per_week, matches_vs_pips_per_week) + value (con số "
        "mục tiêu MỖI TUẦN, thực tế với người đi làm) — metric phải KHỚP đúng "
        "nội dung câu order; app sẽ tự theo dõi tiến độ thật từ database. Không "
        "quy được thì metric=\"\" và value=0.\n"
        "- week_plan: kế hoạch 1 tuần, mỗi ngày có focus + detail (gắn với tập thể lực "
        "và loại trận cần đánh; nhớ giới hạn an toàn đầu gối); 'day' dùng tên thứ "
        "tiếng Việt (Thứ 2 … Chủ nhật).\n"
        "- watch_items: cảnh báo (dữ liệu mỏng/cũ, an toàn, điều cần theo dõi)."
    )
    use_model = model or resolve_model()
    payload = {
        "model": use_model,
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
    log.info("head coach: model=%s took=%.1fs", use_model, time.monotonic() - t0)
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
            use_model = resolve_model()
            row.model = use_model  # record the model actually used
            data = _call_model(
                _bundle_to_text(bundle),
                player_name=bundle.player or "vận động viên",
                model=use_model,
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
        row.directives_json = json.dumps(
            _sanitize_directives(data.get("directives", [])), ensure_ascii=False
        )
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
    # created_at is stored as naive UTC (SQLite drops the tz) — re-attach UTC
    # so the API emits "+00:00" and the browser converts to local (VN) time
    # instead of misreading it as already-local.
    created = row.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=dt.timezone.utc)
    return schemas.AssessmentOut(
        id=row.id,
        created_at=created,
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


# ------------------------------------------------- directive live progress
# Plausible weekly ranges per metric. A model-filled value outside its range is
# nonsense (e.g. "240 coach hours/week") → the metric tag is dropped and the
# directive stays text-only. Defense-in-depth like the video clamps used to be.
_METRIC_RANGE = {
    "physical_sessions_per_week": (1, 7),
    "racket_hours_per_week": (1, 30),
    "coach_hours_per_week": (1, 20),
    "matches_per_week": (1, 40),
    "singles_matches_per_week": (1, 30),
    "doubles_matches_per_week": (1, 30),
    "matches_vs_pips_per_week": (1, 20),
}


def _sanitize_directives(directives: list[dict]) -> list[dict]:
    """Drop implausible machine-trackable tags; never drop the order text."""
    out = []
    for d in directives:
        if not isinstance(d, dict):
            continue
        metric = d.get("metric") or ""
        value = d.get("value")
        rng = _METRIC_RANGE.get(metric)
        ok = (
            rng is not None
            and isinstance(value, (int, float))
            and rng[0] <= float(value) <= rng[1]
        )
        if not ok:
            if metric:
                log.warning(
                    "head coach: dropping implausible directive metric %r=%r",
                    metric, value,
                )
            d = {**d, "metric": "", "value": None}
        d.setdefault("area", "")
        d.setdefault("order", "")
        out.append(d)
    return out


_METRIC_UNIT_VI = {
    "physical_sessions_per_week": "buổi",
    "racket_hours_per_week": "giờ",
    "coach_hours_per_week": "giờ",
    "matches_per_week": "trận",
    "singles_matches_per_week": "trận",
    "doubles_matches_per_week": "trận",
    "matches_vs_pips_per_week": "trận",
}


def _week_actual(db: Session, metric: str, week_start: dt.date, today: dt.date) -> float:
    """This week's (Mon → today) actual for one directive metric, computed
    from the database — never self-reported."""
    if metric == "physical_sessions_per_week":
        return float(
            db.query(TrainingSession)
            .filter(
                TrainingSession.status == "done",
                TrainingSession.done_on >= week_start,
                TrainingSession.done_on <= today,
            )
            .count()
        )
    stats = tracker_service.build_stats(db, week_start, today)
    if metric == "racket_hours_per_week":
        return round(stats.racket_minutes_total / 60, 1)
    if metric == "coach_hours_per_week":
        coach = next(
            (c for c in stats.minutes_by_category if c.key == "train_with_coach"), None
        )
        return round((coach.minutes if coach else 0) / 60, 1)
    if metric == "matches_per_week":
        return float(stats.overall.total)
    if metric == "singles_matches_per_week":
        return float(stats.singles.total)
    if metric == "doubles_matches_per_week":
        return float(stats.doubles.total)
    if metric == "matches_vs_pips_per_week":
        return float(stats.vs_pips.total)
    return 0.0


def directive_progress(db: Session) -> schemas.DirectiveProgressOut:
    """Live progress of the latest verdict's machine-trackable directives:
    this week's database actual vs the weekly target."""
    latest = get_latest(db)
    if latest.empty or latest.id is None:
        return schemas.DirectiveProgressOut()
    today = dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())  # Monday

    items: list[schemas.DirectiveProgress] = []
    for i, d in enumerate(latest.directives):
        if not d.metric or d.metric not in _METRIC_UNIT_VI or not d.value:
            continue
        actual = _week_actual(db, d.metric, week_start, today)
        pct = max(0, min(100, round(100 * actual / d.value)))
        items.append(
            schemas.DirectiveProgress(
                index=i,
                area=d.area,
                order=d.order,
                metric=d.metric,
                value=d.value,
                actual=actual,
                pct=pct,
                unit_vi=_METRIC_UNIT_VI[d.metric],
            )
        )
    return schemas.DirectiveProgressOut(
        assessment_id=latest.id, week_start=week_start, items=items
    )
