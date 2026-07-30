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
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.settings import HEAD_COACH_MODEL, OLLAMA_BASE_URL, TEXT_MODEL
from app.features.head_coach import schemas
from app.features.head_coach.models import CoachChatMessage, CoachNote, HeadCoachAssessment
from app.features.head_coach.prompt import (
    CHAT_RESPONSE_SCHEMA,
    CHAT_SYSTEM_PROMPT,
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
)
from app.features.tournament import service as tournament_service
from app.features.tracker import rating as tracker_rating
from app.features.tracker import service as tracker_service
from app.features.tracker.models import DayNote
from app.features.training import service as training_service
from app.features.training.models import TrainingSession

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
_MIN_SAMPLE_MATCHES = 5

# Relative levels are derived from POINTS vs the athlete's dynamic ELO
# (hand-picked labels retired 2026-07-27); "unrated" = no points entered yet.
_LEVEL_VI = {
    "below": "dưới cơ",
    "equal": "ngang cơ",
    "above": "trên cơ",
    "unrated": "chưa có điểm",
}
_HANDICAP_VI = {
    "even": "đánh đồng",
    "receive": "học trò ĐƯỢC CHẤP",
    "give": "học trò CHẤP đối thủ",
}


# ---------------------------------------------------------------- gather inputs
def _ms(m) -> dict:
    return {"played": m.total, "wins": m.wins, "losses": m.losses, "win_rate": m.win_rate}


def _player_name(db: Session) -> str:
    """The player's name, read straight from the retired profile table.

    The video_analysis feature was deleted (2026-07-29) but its va_profile row
    is user data and stays in SQLite; this is the one field the coach needs.
    """
    try:
        row = db.execute(text("SELECT name FROM va_profile WHERE id = 1")).first()
        return row[0] if row and row[0] else "the player"
    except Exception:
        return "the player"


def _training_summary(training) -> dict:
    """The Training Center facts the coach reads (physical load/adherence)."""
    return {
        "level": training.current_level_vi,
        "total_sessions_done": training.total_sessions_done,
        "sessions_last_7d": training.sessions_last_7d,
        "sessions_last_30d": training.sessions_last_30d,
        "days_since_last": training.days_since_last,
        "current_streak": training.current_streak,
        "intensity_bias": training.intensity_bias,
        "muscle_volume": {mv.muscle: mv.times for mv in training.muscle_volume},
        # NOTE: summary_vi (English GUI prose) is deliberately NOT fed to the
        # coach — its Vietnamese prompt gets the raw numbers above instead.
    }


def _match_summary(
    db: Session, today: dt.date, rep: "tracker_rating.ReplayResult"
) -> dict:
    """Volume + per-discipline results over the stats window, plus the
    dynamic ELO (the coach's objective progress yardstick) and its weekly
    trend — the DIRECTION matters more than any single number."""
    date_from = today - dt.timedelta(days=_STATS_WINDOW_DAYS)
    stats = tracker_service.build_stats(db, date_from, today)
    out = {
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
        "one_v_two": _ms(stats.one_v_two),
        "two_v_one": _ms(stats.two_v_one),
        "vs_pips": _ms(stats.vs_pips),
    }
    my_elo = tracker_service.compute_my_rating(db, replay_result=rep)
    # with_movers=False: the bundle reads only the weekly buckets — no need
    # to build a per-match row for every counted match.
    elo_trend = tracker_service.build_rating_breakdown(
        db, today - dt.timedelta(days=41), today, unit="week", replay=rep,
        with_movers=False,
    )
    out["my_elo"] = {
        "current": my_elo.current,
        "anchor": my_elo.points,
        "anchor_date": my_elo.anchor_date,
        "counted_matches": my_elo.counted_matches,
        "to_rank_e": max(0, tracker_rating.RANK_E_FLOOR - my_elo.current),
        "weekly": [
            {
                "from": b.date_from.isoformat(),
                "to": b.date_to.isoformat(),
                "delta": b.delta,
                "counted": b.counted,
                "rating_end": b.rating_end,
            }
            for b in elo_trend.buckets
            if b.rating_end is not None  # weeks fully before the anchor: no rating
        ],
    }
    return out


def _match_detail(
    db: Session, today: dt.date, rep: "tracker_rating.ReplayResult"
) -> dict:
    """Named-opponent analytics: level × handicap splits, per-kind results,
    monthly trend and the most-played singles head-to-heads (problem
    opponents float up via win_rate)."""
    detail_from = today - dt.timedelta(days=_MATCH_DETAIL_DAYS)
    # form_seed=False: the bundle's trend reads W/L/win_rate only — skip the
    # rolling-form seed query (×4 here, one per kind).
    def _stats(category: str):
        return tracker_service.build_match_stats(
            db, detail_from, today, "all", category, "month",
            replay=rep, form_seed=False,
        )

    detail = _stats("all")
    practice = _stats("practice")
    official = _stats("official")
    tournament = _stats("tournament")
    top_h2h = sorted(detail.singles_h2h, key=lambda r: -r.played)[:8]
    return {
        "window": f"{detail.date_from.isoformat()} → {detail.date_to.isoformat()}",
        # Level × handicap direction (even / receiving / giving points): a
        # handicapped match must be read differently from an even one.
        # (The plain by-level split was dropped 2026-07-29 with its GUI —
        # this table still carries per-level context, ELO covers the rest.)
        "by_level_handicap": tracker_service.build_handicap_split(
            db, detail_from, today, replay=rep
        ),
        # Kinds: practice = đánh chơi, official = đánh độ nhẹ, tournament =
        # đánh giải (new 2026-07-26 — zero rows until the user logs one).
        "practice": _ms(practice.overall),
        "official": _ms(official.overall),
        "tournament": _ms(tournament.overall),
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


def gather_bundle(db: Session) -> schemas.SourceSummary:
    """Assemble the coach's inputs — hard facts from the database ONLY.

    Sources: the Daily Tracker (per-day volume + every match with its score,
    opponent level, pips, practice/official) and the Training Center (physical
    load, adherence, pain). No AI-derived skill ratings: the retired technique-
    analysis pipeline produced model guesses, not observations."""
    today = dt.date.today()

    # ONE ELO replay shared by every rating-dependent build below — the bundle
    # runs on every verdict AND every chat message, and a replay walks every
    # match since the anchor.
    rep = tracker_rating.replay(db)

    training_sum = _training_summary(training_service.report(db))
    match_sum = _match_summary(db, today, rep)
    match_detail = _match_detail(db, today, rep)

    # The player's own day notes — human observations, newest first.
    notes = [
        {"date": n.date.isoformat(), "text": n.text}
        for n in db.query(DayNote).order_by(DayNote.date.desc()).limit(_RECENT_NOTES).all()
    ]

    # The coach's notebook — goals/deadlines/constraints agreed in chat (or
    # added by the player). Oldest first so later notes read as refinements.
    coach_notes = [
        {"date": n.created_at.date().isoformat() if n.created_at else "", "text": n.text}
        for n in db.query(CoachNote).order_by(CoachNote.created_at.asc()).all()
    ]

    return schemas.SourceSummary(
        player=_player_name(db),
        training=training_sum,
        match=match_sum,
        match_detail=match_detail,
        notes=notes,
        coach_notes=coach_notes,
        # Registered upcoming competitions — the week plan aims at these.
        tournaments=tournament_service.upcoming_for_coach(db),
        generated_for_range=(
            f"{(today - dt.timedelta(days=_STATS_WINDOW_DAYS)).isoformat()}"
            f" → {today.isoformat()}"
        ),
    )


def _wr(d: dict) -> str:
    wr = d.get("win_rate")
    wr_s = f"{round(wr * 100)}%" if wr is not None else "—"
    played = d.get("played", 0)
    line = f"{played} trận (T{d.get('wins', 0)}/B{d.get('losses', 0)}, thắng {wr_s})"
    # Small samples are labelled so the model is barred from concluding on them.
    if 0 < played < _MIN_SAMPLE_MATCHES:
        line += " [MẪU NHỎ]"
    return line


def _elo_line(m: dict) -> str:
    """One context line for the user's dynamic ELO. Empty string for old
    snapshots stored before the rating existed (they must keep rendering)."""
    elo = m.get("my_elo") or {}
    if not elo:
        return ""
    line = (
        f"ĐIỂM ELO ĐỘNG của học trò: {elo.get('current')} "
        f"(neo {elo.get('anchor')} từ {elo.get('anchor_date')}, "
        f"đã tính {elo.get('counted_matches')} trận)"
    )
    to_e = elo.get("to_rank_e")
    if to_e:
        line += f" · còn {to_e} điểm nữa tới hạng E"

    def _dm(iso: str) -> str:  # "2026-07-21" → "21/07"
        return f"{iso[8:10]}/{iso[5:7]}"

    weekly = elo.get("weekly") or []
    if weekly:
        parts = []
        for w in weekly:
            d = w.get("delta", 0)
            parts.append(
                f"{_dm(w['from'])}–{_dm(w['to'])}: {'+' if d > 0 else ''}{d} "
                f"({w.get('counted')} trận, cuối tuần {w.get('rating_end')})"
            )
        line += "\nDiễn biến ELO theo TUẦN (cũ → mới): " + " · ".join(parts)
    return line + "\n"


def _bundle_to_text(b: schemas.SourceSummary) -> str:
    """Render the bundle into the Vietnamese context block fed to the model.
    Every number here is computed by code from the database — the model only
    has to reason over the facts, never derive them."""
    t, m, d = b.training, b.match, b.match_detail

    minutes_cat = "; ".join(f"{k}: {v_}p" for k, v_ in m.get("minutes_by_category", {}).items()) or "—"
    muscle = "; ".join(f"{k}×{v_}" for k, v_ in t.get("muscle_volume", {}).items()) or "—"

    hdc = d.get("by_level_handicap", {})
    hdc_lines = "\n".join(
        f"  - Đối thủ {_LEVEL_VI.get(lv, lv)} · {_HANDICAP_VI[dr]}: {_wr(cell)}"
        for lv in ("below", "equal", "above", "unrated")
        for dr in ("even", "receive", "give")
        for cell in [hdc.get(lv, {}).get(dr)]
        if cell
    ) or "  (chưa có dữ liệu)"

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

    def _tour_line(t: dict) -> str:
        d = t.get("days_left", 0)
        when = (
            "ĐANG DIỄN RA"
            if d < 0
            else ("HÔM NAY" if d == 0 else f"còn {d} ngày (bắt đầu {t.get('start_date')})")
        )
        loc = f" tại {t['location']}" if t.get("location") else ""
        limit = f" Giới hạn trình: {t['level_limit']}." if t.get("level_limit") else ""
        entries = "; ".join(t.get("entries", [])) or "chưa ghi nội dung"
        note = f" Ghi chú: {t['note']}" if t.get("note") else ""
        return f"  - {t.get('name')}{loc}: {when}.{limit} Nội dung: {entries}.{note}"

    tour_lines = "\n".join(_tour_line(t) for t in b.tournaments) or (
        "  (chưa đăng ký giải nào)"
    )

    note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.notes
    ) or "  (không có ghi chú)"

    coach_note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.coach_notes
    ) or "  (sổ tay trống)"

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
        f"1v2 (học trò đánh 1 MÌNH vs 2 người): {_wr(m.get('one_v_two', {}))}\n"
        f"2v1 (học trò + đồng đội vs 1 người): {_wr(m.get('two_v_one', {}))}\n"
        f"Gặp đối thủ đánh gai: {_wr(m.get('vs_pips', {}))}\n"
        f"Tổng các trận: {_wr(m.get('overall', {}))}\n"
        f"{_elo_line(m)}\n"
        f"=== PHÂN TÍCH TRẬN SÂU (cửa sổ {d.get('window')}, trận có tên đối thủ) ===\n"
        f"Tách theo hạng đối thủ và CHẤP (điểm chấp mỗi ván; trận có chấp phải diễn giải khác "
        f"trận đánh đồng):\n{hdc_lines}\n"
        f"THEO LOẠI TRẬN: đánh chơi (tập) {_wr(d.get('practice', {}))} · "
        f"đánh độ nhẹ {_wr(d.get('official', {}))} · "
        f"đánh giải (tournament) {_wr(d.get('tournament', {}))}\n"
        f"Xu hướng theo tháng:\n{trend_lines}\n"
        f"Đối đầu nhiều nhất (head-to-head, đơn):\n{h2h_lines}\n\n"
        f"=== THỂ LỰC (Training Center) ===\n"
        f"Cấp độ: {t.get('level')}; tổng buổi đã xong: {t.get('total_sessions_done')}; "
        f"7 ngày: {t.get('sessions_last_7d')} buổi; 30 ngày: {t.get('sessions_last_30d')} buổi; "
        f"chuỗi hiện tại: {t.get('current_streak')} ngày; "
        f"số ngày từ buổi gần nhất: {t.get('days_since_last')}; "
        f"điều chỉnh cường độ: {t.get('intensity_bias')}.\n"
        f"Khối lượng theo nhóm cơ: {muscle}\n\n"
        f"=== GIẢI ĐẤU SẮP TỚI (học trò đã đăng ký) ===\n"
        f"{tour_lines}\n\n"
        f"=== GHI CHÚ HẰNG NGÀY CỦA HỌC TRÒ (mới nhất trước) ===\n"
        f"{note_lines}\n\n"
        f"=== SỔ TAY HLV (mục tiêu/mốc thời gian/ràng buộc đã chốt với học trò) ===\n"
        f"{coach_note_lines}\n"
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


def _ollama_chat(
    model: str, messages: list[dict], schema: dict, temperature: float, tag: str
) -> dict:
    """One non-streaming structured-output call against the local Ollama chat
    API — the single place that owns the payload shape / timeout / num_ctx."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": schema,
        "options": {"temperature": temperature, "num_ctx": 16384},
    }
    t0 = time.monotonic()
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=600.0)
    resp.raise_for_status()
    log.info("%s: model=%s took=%.1fs", tag, model, time.monotonic() - t0)
    content = resp.json().get("message", {}).get("content", "{}")
    return json.loads(content) if content else {}


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
        "liệu. Nếu mệnh lệnh quy được về CHỈ TIÊU TUẦN thì điền metric + value "
        "(con số mục tiêu MỖI TUẦN, thực tế với người đi làm); app sẽ tự theo "
        "dõi tiến độ thật từ database. ĐỊNH NGHĨA metric — app đo ĐÚNG như sau, "
        "nên câu order phải mô tả đúng phạm vi này, không được lệch nghĩa:\n"
        "  * physical_sessions_per_week: số buổi thể lực hoàn thành (Training Center).\n"
        "  * racket_hours_per_week: TỔNG giờ cầm vợt = tập với HLV + tập với "
        "partner + thời gian thi đấu (quy đổi từ số set). Chọn metric này thì "
        "order phải nói rõ 'tổng thời gian cầm vợt (kể cả thi đấu)'.\n"
        "  * coach_hours_per_week: CHỈ riêng giờ tập với HLV.\n"
        "  * matches_per_week: tổng số trận (cả đơn lẫn đôi); "
        "singles_matches_per_week: chỉ trận đơn; doubles_matches_per_week: chỉ "
        "trận đôi; matches_vs_pips_per_week: chỉ trận gặp đối thủ đánh gai.\n"
        "  Không quy được về các metric trên thì metric=\"\" và value=0.\n"
        "- week_plan: kế hoạch 1 tuần, mỗi ngày có focus + detail (gắn với tập thể lực "
        "và loại trận cần đánh; nhớ giới hạn an toàn đầu gối); 'day' dùng tên thứ "
        "tiếng Việt (Thứ 2 … Chủ nhật).\n"
        "- watch_items: cảnh báo (dữ liệu mỏng/cũ, an toàn, điều cần theo dõi)."
    )
    return _ollama_chat(
        model or resolve_model(),
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        RESPONSE_SCHEMA,
        temperature=0.3,
        tag="head coach",
    )


def _call_with_empty_retry(call, key: str, tag: str, model: str) -> dict:
    """Run a structured-output call; retry ONCE when the payload's `key` field
    comes back blank. The first call right after the model loads can return an
    empty object (seen in smoke tests); once warm it answers fine."""
    data = call()
    if not (data.get(key) or "").strip():
        log.warning("%s: empty %r from %s, retrying once", tag, key, model)
        data = call()
    return data


def recover_stuck_jobs(db: Session) -> None:
    """Mark rows orphaned by a crash/restart as errors (run at startup).

    Background jobs die with the process. A verdict left `generating` keeps
    the GUI's Generate button disabled forever, and a chat reply left
    `pending` blocks the chat input AND every new POST /chat (409) — with no
    job alive to ever finish them. Flip them to a visible error instead."""
    msg = "Server restarted trong lúc đang chạy — bấm chạy lại."
    stuck_rows = (
        db.query(HeadCoachAssessment)
        .filter(HeadCoachAssessment.status == "generating")
        .all()
    )
    stuck_chats = (
        db.query(CoachChatMessage)
        .filter(CoachChatMessage.status == "pending")
        .all()
    )
    for row in stuck_rows + stuck_chats:
        row.status = "error"
        row.error_msg = msg
    if stuck_rows or stuck_chats:
        log.warning(
            "head coach: recovered %d stuck assessment(s) + %d stuck chat row(s)",
            len(stuck_rows), len(stuck_chats),
        )
        db.commit()


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

            def call() -> dict:
                out = _call_model(
                    _bundle_to_text(bundle),
                    player_name=bundle.player or "vận động viên",
                    model=use_model,
                )
                return out if isinstance(out, dict) else {}

            data = _call_with_empty_retry(
                call, "overall_assessment", "head coach", use_model
            )
            if not (data.get("overall_assessment") or "").strip():
                raise ValueError("Model trả về bản đánh giá rỗng.")

            # Persistence stays inside the try: a failure here (busy DB,
            # bad payload) must mark the row `error`, never leave it stuck
            # in `generating` with no job alive to finish it.
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
        except Exception as exc:  # noqa: BLE001 — surfaced to the GUI via status
            log.exception("head coach generate(%d) failed", assessment_id)
            db.rollback()
            row = db.get(HeadCoachAssessment, assessment_id)
            if row is not None:
                row.status = "error"
                row.error_msg = str(exc)[:1000]
                db.commit()
            return
    finally:
        db.close()


def _to_out(row: HeadCoachAssessment) -> schemas.AssessmentOut:
    return schemas.AssessmentOut(
        id=row.id,
        created_at=_tz(row.created_at),
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
    "physical_sessions_per_week": "sessions",
    "racket_hours_per_week": "hours",
    "coach_hours_per_week": "hours",
    "matches_per_week": "matches",
    "singles_matches_per_week": "matches",
    "doubles_matches_per_week": "matches",
    "matches_vs_pips_per_week": "matches",
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


# ------------------------------------------------------------------ coach chat
# Char budget for the verbatim history injected per reply. The FULL history
# always lives in the DB; this only bounds what goes into one model call
# (~8k chars of chat + ~3k bundle fits far inside num_ctx=16384). At the
# user's current volume this truncates nothing for a very long time.
_CHAT_HISTORY_CHAR_BUDGET = 8000
# Guardrails on the auto-written notebook (per reply).
_MAX_NOTES_PER_REPLY = 3
_MAX_NOTE_CHARS = 300


def _tz(created: dt.datetime | None) -> dt.datetime | None:
    """Re-attach UTC to a naive SQLite timestamp (same fix as _to_out)."""
    if created is not None and created.tzinfo is None:
        return created.replace(tzinfo=dt.timezone.utc)
    return created


def _msg_out(row: CoachChatMessage) -> schemas.ChatMessageOut:
    return schemas.ChatMessageOut(
        id=row.id,
        created_at=_tz(row.created_at),
        role=row.role,
        content=row.content,
        status=row.status or "done",
        error_msg=row.error_msg,
        model=row.model or "",
    )


def chat_history(db: Session) -> schemas.ChatHistoryOut:
    rows = db.query(CoachChatMessage).order_by(CoachChatMessage.id.asc()).all()
    return schemas.ChatHistoryOut(
        messages=[_msg_out(r) for r in rows],
        pending=any(r.status == "pending" for r in rows),
    )


def start_chat(db: Session, text: str) -> schemas.ChatHistoryOut:
    """Store the player's message + a pending coach row; the reply is filled
    by run_chat_job on a background task (same pattern as the verdict).
    Refuses while a reply is already in flight — one question at a time."""
    pending = (
        db.query(CoachChatMessage).filter(CoachChatMessage.status == "pending").first()
    )
    if pending is not None:
        raise ValueError("HLV đang trả lời câu trước — chờ xong rồi gửi tiếp.")
    db.add(CoachChatMessage(role="user", content=text.strip(), status="done"))
    db.add(CoachChatMessage(role="coach", content="", status="pending"))
    db.commit()
    return chat_history(db)


def _history_for_prompt(rows: list[CoachChatMessage]) -> list[dict]:
    """The chat history as Ollama messages, newest-first budgeted then
    restored to chronological order. Only completed turns are included."""
    picked: list[dict] = []
    used = 0
    for r in reversed(rows):
        if r.status != "done" or not r.content:
            continue
        if used + len(r.content) > _CHAT_HISTORY_CHAR_BUDGET and picked:
            break
        used += len(r.content)
        picked.append(
            {"role": "user" if r.role == "user" else "assistant", "content": r.content}
        )
    return list(reversed(picked))


def _call_chat_model(
    context_text: str, history: list[dict], question: str, model: str
) -> dict:
    """One grounded chat turn → {"reply": str, "new_notes": [str]}."""
    grounding = (
        "DỮ LIỆU THẬT MỚI NHẤT của học trò (code tính từ cơ sở dữ liệu, kèm SỔ "
        "TAY của bạn ở cuối). Dùng làm căn cứ cho MỌI nhận định:\n\n"
        f"{context_text}"
    )
    messages = (
        [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": grounding},
            {
                "role": "assistant",
                "content": "Tôi đã nắm toàn bộ số liệu và sổ tay. Mời anh nói.",
            },
        ]
        + history
        + [{"role": "user", "content": question}]
    )
    return _ollama_chat(
        model, messages, CHAT_RESPONSE_SCHEMA, temperature=0.4, tag="coach chat"
    )


def _save_new_notes(db: Session, raw_notes) -> None:
    """Auto-write the notebook (user's choice: no confirmation step), with
    guardrails: cap count/length, skip blanks and case-insensitive duplicates."""
    if not isinstance(raw_notes, list):
        return
    existing = {n.text.strip().lower() for n in db.query(CoachNote).all()}
    saved = 0
    for raw in raw_notes:
        if saved >= _MAX_NOTES_PER_REPLY:
            break
        if not isinstance(raw, str):
            continue
        text = raw.strip()[:_MAX_NOTE_CHARS]
        if not text or text.lower() in existing:
            continue
        db.add(CoachNote(text=text, source="chat"))
        existing.add(text.lower())
        saved += 1


def run_chat_job(db_or_none: Session | None = None) -> None:
    """Background job: answer the oldest pending coach message.

    Injects the live bundle (with notebook) + the verbatim history from the
    DB, calls the model, saves the reply and auto-writes any new notes."""
    db = db_or_none or SessionLocal()
    try:
        row = (
            db.query(CoachChatMessage)
            .filter(CoachChatMessage.status == "pending", CoachChatMessage.role == "coach")
            .order_by(CoachChatMessage.id.asc())
            .first()
        )
        if row is None:
            return
        try:
            all_rows = (
                db.query(CoachChatMessage)
                .filter(CoachChatMessage.id < row.id)
                .order_by(CoachChatMessage.id.asc())
                .all()
            )
            # The newest user message is the question; everything before it
            # is history.
            question_row = all_rows[-1] if all_rows else None
            if question_row is None or question_row.role != "user":
                raise ValueError("no user question found for the pending reply")
            bundle = gather_bundle(db)
            use_model = resolve_model()
            row.model = use_model
            def call() -> dict:
                # Coerce non-dict JSON to {} — `data` is read after the try
                # block, so it must always be a dict.
                out = _call_chat_model(
                    _bundle_to_text(bundle),
                    history=_history_for_prompt(all_rows[:-1]),
                    question=question_row.content,
                    model=use_model,
                )
                return out if isinstance(out, dict) else {}
            data = _call_with_empty_retry(call, "reply", "coach chat", use_model)
        except Exception as exc:  # noqa: BLE001 — surfaced to the GUI via status
            log.exception("coach chat reply failed")
            db.rollback()
            row = (
                db.query(CoachChatMessage)
                .filter(CoachChatMessage.status == "pending", CoachChatMessage.role == "coach")
                .order_by(CoachChatMessage.id.asc())
                .first()
            )
            if row is not None:
                row.status = "error"
                row.error_msg = str(exc)[:1000]
                db.commit()
            return
        row.content = (data.get("reply") or "").strip()
        if not row.content:
            row.status = "error"
            row.error_msg = "Model trả về câu trả lời rỗng."
        else:
            row.status = "done"
            row.error_msg = None
            _save_new_notes(db, data.get("new_notes"))
        db.commit()
    finally:
        if db_or_none is None:
            db.close()


# --------------------------------------------------------------- coach notebook
def list_notes(db: Session) -> schemas.NotesOut:
    rows = db.query(CoachNote).order_by(CoachNote.created_at.desc(), CoachNote.id.desc()).all()
    return schemas.NotesOut(
        notes=[
            schemas.NoteOut(
                id=r.id, created_at=_tz(r.created_at), text=r.text, source=r.source
            )
            for r in rows
        ]
    )


def add_note(db: Session, text: str) -> schemas.NotesOut:
    db.add(CoachNote(text=text.strip(), source="user"))
    db.commit()
    return list_notes(db)


def delete_note(db: Session, note_id: int) -> schemas.NotesOut:
    """Player-initiated removal of one notebook entry (explicit UI action)."""
    row = db.get(CoachNote, note_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return list_notes(db)


# --------------------------------------------------------------- dev log panel
def debug_info() -> schemas.DebugOut:
    """Recent backend log lines + which models Ollama currently holds in
    VRAM — enough to diagnose OOM (something else hogging the GPU), model
    fallback, retries and slow generations from the browser."""
    from app.core import logbuffer  # local import: keeps tests decoupled

    out = schemas.DebugOut(logs=logbuffer.tail())
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=5.0)
        resp.raise_for_status()
        out.ollama_ok = True
        for m in resp.json().get("models", []):
            out.loaded_models.append(
                schemas.OllamaModelPs(
                    name=m.get("name", ""),
                    size_mb=int(m.get("size", 0) / 1_048_576),
                    size_vram_mb=int(m.get("size_vram", 0) / 1_048_576),
                    expires_at=str(m.get("expires_at", "")),
                )
            )
    except Exception as exc:  # noqa: BLE001 — the panel must render regardless
        out.ollama_error = str(exc)[:300]
    return out
