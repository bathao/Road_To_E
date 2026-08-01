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
from app.features.head_coach.models import (
    CoachChatMessage,
    CoachNote,
    HeadCoachAssessment,
    HeadCoachRecap,
)
from app.features.head_coach.prompt import (
    CHAT_RESPONSE_SCHEMA,
    CHAT_SYSTEM_PROMPT,
    RECAP_RESPONSE_SCHEMA,
    RECAP_SYSTEM_PROMPT,
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
)
from app.features.tournament import service as tournament_service
from app.features.tracker import rating as tracker_rating
from app.features.tracker import service as tracker_service
from app.features.tracker.models import Activity, DayNote, Match, PhysicalCheck, SessionNote
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

    # What the REAL-LIFE coach is asking for (all still-active advice, oldest
    # first) + what recent coach sessions covered (recaps, newest first).
    def _sn(n: SessionNote) -> dict:
        tags = [t for t in (n.tags or "").split(",") if t]
        return {
            "date": n.date.isoformat(),
            "text": n.text,
            "tags": [tracker_service.SESSION_NOTE_TAG_LABELS.get(t, t) for t in tags],
        }

    coach_advice = [_sn(n) for n in tracker_service.list_active_advice(db)]
    # Drills count as recap material (what was actually practiced) — prefixed
    # so the model can tell one exercise from an overall summary.
    session_recaps = [
        _sn(n)
        | (
            {"text": f"Bài tập: {n.text}"}
            if n.kind == tracker_service.SN_KIND_DRILL
            else {}
        )
        for n in db.query(SessionNote)
        .filter(SessionNote.kind != tracker_service.SN_KIND_ADVICE)
        .order_by(SessionNote.date.desc(), SessionNote.id.desc())
        .limit(_RECENT_NOTES)
        .all()
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
        coach_advice=coach_advice,
        session_recaps=session_recaps,
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

    def _sn_line(n: dict) -> str:
        tag_s = f" [{', '.join(n['tags'])}]" if n.get("tags") else ""
        return f"  - {n['date']}{tag_s}: {n['text']}"

    advice_lines = "\n".join(_sn_line(n) for n in b.coach_advice) or (
        "  (không có lời dặn nào đang mở)"
    )
    recap_lines = "\n".join(_sn_line(n) for n in b.session_recaps) or (
        "  (chưa có recap buổi tập nào)"
    )

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
        f"=== HLV TRỰC TIẾP ĐANG DẶN (học trò ghi lại; chưa hoàn thành — cần tập tiếp) ===\n"
        f"{advice_lines}\n\n"
        f"=== RECAP CÁC BUỔI TẬP VỚI HLV TRỰC TIẾP (mới nhất trước) ===\n"
        f"{recap_lines}\n\n"
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
    stuck_recaps = (
        db.query(HeadCoachRecap)
        .filter(HeadCoachRecap.status == "generating")
        .all()
    )
    for row in stuck_rows + stuck_chats + stuck_recaps:
        row.status = "error"
        row.error_msg = msg
    if stuck_rows or stuck_chats or stuck_recaps:
        log.warning(
            "head coach: recovered %d stuck assessment(s) + %d stuck chat row(s)"
            " + %d stuck recap(s)",
            len(stuck_rows), len(stuck_chats), len(stuck_recaps),
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


# ------------------------------------------------------- weekly/monthly recap
# The recap looks back over a ROLLING window ending TODAY — week = the last
# 7 days, month = the last 30 days, results up to the moment the button is
# pressed (redesigned 2026-08-01; the original closed-calendar-period +
# lazy-auto-generate version was cut on first contact — the user wants an
# explicit button, exactly like the verdict's Re-analyze).
_RECAP_PERIODS = ("week", "month")
_RECAP_WINDOW_DAYS = {"week": 7, "month": 30}
# Most-played in-period head-to-heads fed to the recap prompt.
_RECAP_H2H = 5


def _period_label_vi(period_type: str, start: dt.date, end: dt.date) -> str:
    days = _RECAP_WINDOW_DAYS.get(period_type, 0)
    return f"{days} NGÀY GẦN NHẤT ({start.isoformat()} → {end.isoformat()})"


def _period_has_data(db: Session, start: dt.date, end: dt.date) -> bool:
    """Whether anything was tracked inside the period (mirrors the sources of
    tracker_service.earliest_data_date) — an empty period is never recapped."""
    for model, col in (
        (Activity, Activity.date),
        (Match, Match.date),
        (PhysicalCheck, PhysicalCheck.date),
    ):
        if db.query(model.id).filter(col >= start, col <= end).first() is not None:
            return True
    return (
        db.query(TrainingSession.id)
        .filter(
            TrainingSession.status == "done",
            TrainingSession.done_on >= start,
            TrainingSession.done_on <= end,
        )
        .first()
        is not None
    )


def _period_stats(
    db: Session, start: dt.date, end: dt.date, rep: "tracker_rating.ReplayResult"
) -> tuple:
    """Code-computed snapshot for one period (+ the full StatsResponse so the
    bundle can reuse it without querying twice)."""
    stats = tracker_service.build_stats(db, start, end)
    elo = tracker_service.build_rating_breakdown(
        db, start, end, unit="week", replay=rep, with_movers=False
    )
    physical_sessions = (
        db.query(TrainingSession)
        .filter(
            TrainingSession.status == "done",
            TrainingSession.done_on >= start,
            TrainingSession.done_on <= end,
        )
        .count()
    )
    snapshot = schemas.RecapPeriodStats(
        date_from=start,
        date_to=end,
        days_trained=stats.days_trained,
        days_physical=stats.days_physical,
        minutes_total=stats.minutes_total,
        racket_minutes_total=stats.racket_minutes_total,
        matches_played=stats.overall.total,
        matches_wins=stats.overall.wins,
        matches_losses=stats.overall.losses,
        win_rate=stats.overall.win_rate,
        elo_delta=elo.total_delta,
        elo_end=elo.rating_end,
        elo_counted=elo.counted,
        physical_sessions=physical_sessions,
    )
    return snapshot, stats


def gather_recap_bundle(
    db: Session,
    period_type: str,
    start: dt.date,
    end: dt.date,
    rep: "tracker_rating.ReplayResult",
    stats: schemas.RecapStats,
    full_stats,
) -> dict:
    """The recap's inputs: the code-computed snapshot pair + in-period detail
    (per-discipline/kind results, ELO buckets, h2h, notes, coach sessions)."""
    detail = tracker_service.build_match_stats(
        db, start, end, "all", "all", "week", replay=rep, form_seed=False
    )

    def _kind(category: str) -> dict:
        return _ms(
            tracker_service.build_match_stats(
                db, start, end, "all", category, "week", replay=rep, form_seed=False
            ).overall
        )

    elo = tracker_service.build_rating_breakdown(
        db, start, end, unit="week", replay=rep, with_movers=False
    )
    top_h2h = sorted(detail.singles_h2h, key=lambda r: -r.played)[:_RECAP_H2H]

    def _sn(n: SessionNote) -> dict:
        tags = [t for t in (n.tags or "").split(",") if t]
        return {
            "date": n.date.isoformat(),
            "kind": n.kind,
            "text": n.text,
            "tags": [tracker_service.SESSION_NOTE_TAG_LABELS.get(t, t) for t in tags],
        }

    session_notes = [
        _sn(n)
        for n in db.query(SessionNote)
        .filter(SessionNote.date >= start, SessionNote.date <= end)
        .order_by(SessionNote.date.asc(), SessionNote.id.asc())
        .all()
    ]
    day_notes = [
        {"date": n.date.isoformat(), "text": n.text}
        for n in db.query(DayNote)
        .filter(DayNote.date >= start, DayNote.date <= end)
        .order_by(DayNote.date.asc())
        .all()
    ]
    coach_notes = [
        {"date": n.created_at.date().isoformat() if n.created_at else "", "text": n.text}
        for n in db.query(CoachNote).order_by(CoachNote.created_at.asc()).all()
    ]

    return {
        "player": _player_name(db),
        "period_type": period_type,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "stats": stats.model_dump(mode="json"),
        "results": {
            "singles": _ms(full_stats.singles),
            "doubles": _ms(full_stats.doubles),
            "one_v_two": _ms(full_stats.one_v_two),
            "two_v_one": _ms(full_stats.two_v_one),
            "vs_pips": _ms(full_stats.vs_pips),
            "overall": _ms(full_stats.overall),
        },
        "by_kind": {
            "practice": _kind("practice"),
            "official": _kind("official"),
            "tournament": _kind("tournament"),
        },
        "minutes_by_category": {
            c.label: c.minutes for c in full_stats.minutes_by_category
        },
        "elo_weekly": [
            {
                "from": b.date_from.isoformat(),
                "to": b.date_to.isoformat(),
                "delta": b.delta,
                "counted": b.counted,
                "rating_end": b.rating_end,
            }
            for b in elo.buckets
            if b.rating_end is not None
        ],
        "top_h2h": [
            {
                "name": r.name,
                "level": r.level,
                "played": r.played,
                "wins": r.wins,
                "losses": r.losses,
            }
            for r in top_h2h
        ],
        "session_notes": session_notes,
        "day_notes": day_notes,
        "coach_notes": coach_notes,
    }


def _snapshot_pair_lines(stats: dict) -> str:
    """Render the current-vs-previous snapshot for the prompt — every number
    computed by code; the model only compares."""
    cur = stats.get("current") or {}
    prev = stats.get("previous")

    def _pair(label: str, key: str, unit: str = "") -> str:
        line = f"- {label}: {cur.get(key, 0)}{unit}"
        if prev is not None:
            line += f" (kỳ trước: {prev.get(key, 0)}{unit})"
        return line

    def _elo(d: dict) -> str:
        if d.get("elo_end") is None:
            return "chưa có ELO (trước mốc neo)"
        delta = d.get("elo_delta", 0)
        return (
            f"{'+' if delta > 0 else ''}{delta} điểm "
            f"({d.get('elo_counted', 0)} trận tính điểm, cuối kỳ {d.get('elo_end')})"
        )

    def _matches(d: dict) -> str:
        wr = d.get("win_rate")
        wr_s = f"{round(wr * 100)}%" if wr is not None else "—"
        return (
            f"{d.get('matches_played', 0)} trận "
            f"(T{d.get('matches_wins', 0)}/B{d.get('matches_losses', 0)}, thắng {wr_s})"
        )

    lines = [
        _pair("Số ngày có hoạt động", "days_trained"),
        _pair("Ngày thể lực", "days_physical"),
        _pair("Buổi thể lực hoàn thành (Training Center)", "physical_sessions"),
        _pair("Phút tập có chủ đích", "minutes_total", "p"),
        _pair("Tổng phút cầm vợt", "racket_minutes_total", "p"),
        f"- Trận đấu: {_matches(cur)}"
        + (f" (kỳ trước: {_matches(prev)})" if prev is not None else ""),
        f"- ELO: {_elo(cur)}" + (f" (kỳ trước: {_elo(prev)})" if prev is not None else ""),
    ]
    if prev is None:
        lines.append("(Kỳ liền trước chưa có dữ liệu theo dõi — không so sánh được.)")
    return "\n".join(lines)


_SN_KIND_VI = {"advice": "HLV dặn", "drill": "Bài tập", "recap": "Recap buổi tập"}


def _recap_bundle_to_text(b: dict) -> str:
    """Render the recap bundle into the Vietnamese context block."""
    label = _period_label_vi(
        b["period_type"],
        dt.date.fromisoformat(b["period_start"]),
        dt.date.fromisoformat(b["period_end"]),
    )
    r = b.get("results", {})
    k = b.get("by_kind", {})

    minutes_cat = "; ".join(
        f"{cat}: {v_}p" for cat, v_ in b.get("minutes_by_category", {}).items()
    ) or "—"

    weekly = b.get("elo_weekly") or []
    elo_lines = ""
    if len(weekly) > 1:  # month recaps: show the week-by-week path
        parts = [
            f"{w['from'][8:10]}/{w['from'][5:7]}–{w['to'][8:10]}/{w['to'][5:7]}: "
            f"{'+' if w['delta'] > 0 else ''}{w['delta']} ({w['counted']} trận, "
            f"cuối tuần {w['rating_end']})"
            for w in weekly
        ]
        elo_lines = "Diễn biến ELO theo tuần trong kỳ: " + " · ".join(parts) + "\n"

    h2h_lines = "\n".join(
        f"  - {p['name']} ({_LEVEL_VI.get(p['level'], p['level'])}): "
        f"{p['played']} trận (T{p['wins']}/B{p['losses']})"
        for p in b.get("top_h2h", [])
    ) or "  (không có trận đơn có tên đối thủ trong kỳ)"

    def _sn_line(n: dict) -> str:
        tag_s = f" [{', '.join(n['tags'])}]" if n.get("tags") else ""
        kind = _SN_KIND_VI.get(n.get("kind", ""), n.get("kind", ""))
        return f"  - {n['date']} · {kind}{tag_s}: {n['text']}"

    sn_lines = "\n".join(_sn_line(n) for n in b.get("session_notes", [])) or (
        "  (không có buổi tập với HLV trực tiếp trong kỳ)"
    )
    note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.get("day_notes", [])
    ) or "  (không có ghi chú)"
    coach_note_lines = "\n".join(
        f"  - {n['date']}: {n['text']}" for n in b.get("coach_notes", [])
    ) or "  (sổ tay trống)"

    return (
        f"Vận động viên: {b.get('player')}.\n"
        f"KỲ TỔNG KẾT: {label}.\n\n"
        f"=== SỐ LIỆU KỲ NÀY (so với KỲ LIỀN TRƯỚC) ===\n"
        f"{_snapshot_pair_lines(b.get('stats', {}))}\n"
        f"Phút tập theo hạng mục (kỳ này): {minutes_cat}\n\n"
        f"=== KẾT QUẢ THI ĐẤU TRONG KỲ ===\n"
        f"Đơn: {_wr(r.get('singles', {}))}\n"
        f"Đôi: {_wr(r.get('doubles', {}))}\n"
        f"1v2 (học trò đánh 1 MÌNH vs 2 người): {_wr(r.get('one_v_two', {}))}\n"
        f"2v1 (học trò + đồng đội vs 1 người): {_wr(r.get('two_v_one', {}))}\n"
        f"Gặp đối thủ đánh gai: {_wr(r.get('vs_pips', {}))}\n"
        f"Tổng các trận: {_wr(r.get('overall', {}))}\n"
        f"THEO LOẠI TRẬN: đánh chơi (tập) {_wr(k.get('practice', {}))} · "
        f"đánh độ nhẹ {_wr(k.get('official', {}))} · "
        f"đánh giải (tournament) {_wr(k.get('tournament', {}))}\n"
        f"{elo_lines}"
        f"Đối đầu nhiều nhất trong kỳ (đơn):\n{h2h_lines}\n\n"
        f"=== HLV TRỰC TIẾP TRONG KỲ (lời dặn / bài tập / recap học trò ghi lại) ===\n"
        f"{sn_lines}\n\n"
        f"=== GHI CHÚ HẰNG NGÀY CỦA HỌC TRÒ TRONG KỲ ===\n"
        f"{note_lines}\n\n"
        f"=== SỔ TAY HLV (mục tiêu/ràng buộc đã chốt — bối cảnh, có thể ngoài kỳ) ===\n"
        f"{coach_note_lines}\n"
    )


def _call_recap_model(
    context_text: str, player_name: str, period_type: str, model: str
) -> dict:
    next_vi = "7 ngày tới" if period_type == "week" else "30 ngày tới"
    user_text = (
        f"Dưới đây là toàn bộ số liệu của học trò {player_name} trong giai đoạn "
        "vừa qua, tính đến HÔM NAY (kèm giai đoạn cùng độ dài liền trước để so "
        "sánh). Hãy tổng kết NGHIÊM KHẮC giai đoạn này.\n\n"
        f"{context_text}\n"
        "Yêu cầu trả về (tiếng Việt, đúng JSON schema):\n"
        "- headline: MỘT câu chốt lại giai đoạn này (trích được con số đắt nhất).\n"
        "- overall: 3-6 câu đánh giá tổng thể giai đoạn này so với giai đoạn "
        "trước — khối lượng, số trận, ELO, mức bám sát lời dặn của HLV trực tiếp.\n"
        "- went_well: những điểm LÀM ĐƯỢC trong giai đoạn (kèm số liệu; không có "
        "thì để mảng rỗng, không bịa).\n"
        "- concerns: những điểm ĐÁNG LO / tụt so với giai đoạn trước (kèm số liệu).\n"
        f"- focus_next: 2-4 việc cụ thể cần dồn sức trong {next_vi} (đo được, "
        "thực tế với người đi làm; không ra lệnh ngược HLV trực tiếp)."
    )
    return _ollama_chat(
        model,
        [
            {"role": "system", "content": RECAP_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        RECAP_RESPONSE_SCHEMA,
        temperature=0.3,
        tag="coach recap",
    )


def _recap_to_out(row: HeadCoachRecap) -> schemas.RecapOut:
    stats_raw = json.loads(row.stats_json or "{}")
    return schemas.RecapOut(
        id=row.id,
        created_at=_tz(row.created_at),
        model=row.model,
        status=row.status or "done",
        error_msg=row.error_msg,
        period_type=row.period_type,
        period_start=row.period_start,
        period_end=row.period_end,
        headline=row.headline,
        overall=row.overall,
        went_well=json.loads(row.went_well_json),
        concerns=json.loads(row.concerns_json),
        focus_next=json.loads(row.focus_next_json),
        stats=schemas.RecapStats(**stats_raw) if stats_raw.get("current") else None,
    )


def get_recaps(db: Session, period_type: str) -> schemas.RecapsOut:
    """The most recently generated recap of one window type — read-only.

    NO auto-generation (user's explicit choice 2026-08-01): generation only
    happens through start_recap when the button is pressed. Older rows stay
    in the DB untouched but are never listed."""
    latest_row = (
        db.query(HeadCoachRecap)
        .filter(HeadCoachRecap.period_type == period_type)
        .order_by(HeadCoachRecap.period_start.desc(), HeadCoachRecap.id.desc())
        .first()
    )
    return schemas.RecapsOut(
        period_type=period_type,
        latest=_recap_to_out(latest_row) if latest_row is not None else None,
    )


def get_recap(db: Session, recap_id: int) -> schemas.RecapOut | None:
    row = db.get(HeadCoachRecap, recap_id)
    return _recap_to_out(row) if row is not None else None


def start_recap(
    db: Session, period_type: str, today: dt.date | None = None
) -> schemas.RecapOut:
    """Start generating a recap of the window ENDING TODAY (last 7/30 days,
    results up to the moment the button is pressed). Pressing again on the
    same day reuses that day's row (regenerate) — no duplicate rows."""
    today = today or dt.date.today()
    if period_type not in _RECAP_PERIODS:
        raise ValueError("period_type must be 'week' or 'month'")
    days = _RECAP_WINDOW_DAYS[period_type]
    start = today - dt.timedelta(days=days - 1)
    in_flight = (
        db.query(HeadCoachRecap)
        .filter(
            HeadCoachRecap.period_type == period_type,
            HeadCoachRecap.status == "generating",
        )
        .first()
    )
    if in_flight is not None:
        raise ValueError("A recap is already being generated — wait for it to finish")
    if not _period_has_data(db, start, today):
        raise ValueError(f"No logged data in the last {days} days — nothing to recap")

    row = (
        db.query(HeadCoachRecap)
        .filter(
            HeadCoachRecap.period_type == period_type,
            HeadCoachRecap.period_start == start,
        )
        .first()
    )
    if row is None:
        row = HeadCoachRecap(period_type=period_type, period_start=start, period_end=today)
        db.add(row)
    row.period_end = today
    row.model = HEAD_COACH_MODEL
    row.status = "generating"
    row.error_msg = None
    row.created_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(row)
    return _recap_to_out(row)


def run_recap_job(recap_id: int, db_or_none: Session | None = None) -> None:
    """Background job: compute the period's stats, call the model, persist.
    Accepts an injected session so tests can run it synchronously."""
    db = db_or_none or SessionLocal()
    try:
        row = db.get(HeadCoachRecap, recap_id)
        if row is None or row.status != "generating":
            return
        try:
            rep = tracker_rating.replay(db)
            cur_snap, full_stats = _period_stats(db, row.period_start, row.period_end, rep)
            # The comparison window: the same number of days right before.
            days = _RECAP_WINDOW_DAYS.get(row.period_type, 7)
            prev_end = row.period_start - dt.timedelta(days=1)
            prev_start = prev_end - dt.timedelta(days=days - 1)
            earliest = tracker_service.earliest_data_date(db)
            prev_snap = None
            if earliest is not None and prev_end >= earliest:
                prev_snap, _ = _period_stats(db, prev_start, prev_end, rep)
            stats = schemas.RecapStats(current=cur_snap, previous=prev_snap)

            bundle = gather_recap_bundle(
                db, row.period_type, row.period_start, row.period_end,
                rep, stats, full_stats,
            )
            use_model = resolve_model()
            row.model = use_model

            def call() -> dict:
                out = _call_recap_model(
                    _recap_bundle_to_text(bundle),
                    player_name=bundle.get("player") or "vận động viên",
                    period_type=row.period_type,
                    model=use_model,
                )
                return out if isinstance(out, dict) else {}

            data = _call_with_empty_retry(call, "overall", "coach recap", use_model)
            if not (data.get("overall") or "").strip():
                raise ValueError("Model trả về bản tổng kết rỗng.")

            # Persistence stays inside the try (same reasoning as the verdict
            # job): a failure must mark the row `error`, never leave it stuck.
            row.headline = (data.get("headline") or "").strip()
            row.overall = data.get("overall", "")
            row.went_well_json = json.dumps(data.get("went_well", []), ensure_ascii=False)
            row.concerns_json = json.dumps(data.get("concerns", []), ensure_ascii=False)
            row.focus_next_json = json.dumps(data.get("focus_next", []), ensure_ascii=False)
            row.stats_json = stats.model_dump_json()
            row.sources_json = json.dumps(bundle, ensure_ascii=False)
            row.status = "done"
            row.error_msg = None
            db.commit()
        except Exception as exc:  # noqa: BLE001 — surfaced to the GUI via status
            log.exception("coach recap(%d) failed", recap_id)
            db.rollback()
            row = db.get(HeadCoachRecap, recap_id)
            if row is not None:
                row.status = "error"
                row.error_msg = str(exc)[:1000]
                db.commit()
            return
    finally:
        if db_or_none is None:
            db.close()


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
