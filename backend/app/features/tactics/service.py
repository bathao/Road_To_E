"""Tactics service: scouting facts + per-opponent game plans.

A consumer like the Head Coach: reads tracker matches in-process, reuses the
head coach's Ollama plumbing (_ollama_chat / resolve_model) and persona, and
persists plans with the same generating→done|error polling contract."""
from __future__ import annotations

import datetime as dt
import json
import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.features.head_coach.service import (
    _coach_note_dicts,
    _hdc_vi,
    _ollama_chat,
    resolve_model,
)
from app.features.tactics import schemas
from app.features.tactics.models import TacticFact, TacticPlan, TacticReflection
from app.features.tactics.prompt import (
    EXTRACT_RESPONSE_SCHEMA,
    EXTRACT_SYSTEM_PROMPT,
    FACT_KINDS,
    INTERVIEW_RESPONSE_SCHEMA,
    INTERVIEW_SYSTEM_PROMPT,
    ME_INTAKE_KEYS,
    OPP_INTAKE_KEYS,
    PLAN_RESPONSE_SCHEMA,
    PLAN_SYSTEM_PROMPT,
)
from app.features.tracker.models import Match, Player
from app.features.tracker.rating import _ROUND_NAME
from app.features.tracker.service import compute_my_rating

log = logging.getLogger(__name__)

# Most recent h2h matches spelled out per prompt (older ones fold into the
# summary counts only).
_H2H_PROMPT_LINES = 30

_KIND_VI = {
    "strength": "Điểm mạnh",
    "weakness": "Điểm yếu",
    "style": "Lối đánh",
    "note": "Ghi chú",
}


# ------------------------------------------------------------- opponent picker
def list_opponents(db: Session) -> list[schemas.OpponentOut]:
    """Everyone the user has PLAYED AGAINST in SINGLES, most matches first —
    the tab's picker. Doubles/1v2/2v1 stay out entirely (user 2026-08-15:
    personal tactics only make sense for singles), and so do partner-only
    people."""
    rows = (
        db.query(Player, Match)
        .filter(
            Match.is_nonplaying == False,  # noqa: E712
            Match.discipline == "singles",
            Match.opponent_id == Player.id,
        )
        .all()
    )
    by_player: dict[int, dict] = {}
    for p, m in rows:
        d = by_player.setdefault(
            p.id,
            {"player": p, "matches_vs": 0, "wins": 0, "losses": 0, "last_vs": m.date},
        )
        d["matches_vs"] += 1
        d["last_vs"] = max(d["last_vs"], m.date)
        if m.my_sets > m.opp_sets:
            d["wins"] += 1
        elif m.my_sets < m.opp_sets:
            d["losses"] += 1
    out = [
        schemas.OpponentOut(
            id=d["player"].id,
            name=d["player"].name,
            points=d["player"].points,
            plays_pips=bool(d["player"].plays_pips),
            matches_vs=d["matches_vs"],
            wins=d["wins"],
            losses=d["losses"],
            last_vs=d["last_vs"],
        )
        for d in by_player.values()
    ]
    out.sort(
        key=lambda o: (-o.matches_vs, -(o.last_vs.toordinal() if o.last_vs else 0))
    )
    return out


# ---------------------------------------------------------------- scouting facts
def list_facts(db: Session, player_id: int) -> schemas.FactsOut:
    rows = (
        db.query(TacticFact)
        .filter(or_(TacticFact.player_id.is_(None), TacticFact.player_id == player_id))
        .order_by(TacticFact.id)
        .all()
    )
    return schemas.FactsOut(
        me=[schemas.FactOut.model_validate(r) for r in rows if r.player_id is None],
        opponent=[
            schemas.FactOut.model_validate(r) for r in rows if r.player_id is not None
        ],
    )


def add_fact(
    db: Session, payload: schemas.FactIn, source: str = "user"
) -> TacticFact:
    """Free-form facts append; keyed (intake) facts upsert on (player_id,
    key) — re-answering an intake question edits the row instead of piling
    up duplicates."""
    if payload.key is not None:
        row = (
            db.query(TacticFact)
            .filter(
                TacticFact.player_id.is_(None)
                if payload.player_id is None
                else TacticFact.player_id == payload.player_id,
                TacticFact.key == payload.key,
            )
            .first()
        )
        if row is not None:
            row.kind = payload.kind
            row.text = payload.text
            db.commit()
            db.refresh(row)
            return row
    row = TacticFact(
        player_id=payload.player_id,
        kind=payload.kind,
        text=payload.text,
        source="intake" if payload.key is not None else source,
        key=payload.key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_fact(db: Session, fact_id: int, payload: schemas.FactUpdate) -> TacticFact:
    row = db.get(TacticFact, fact_id)
    if row is None:
        raise LookupError("Fact not found")
    if payload.kind is not None:
        row.kind = payload.kind
    if payload.text is not None:
        text = payload.text.strip()
        if not text:
            raise ValueError("Fact text cannot be empty.")
        row.text = text
    db.commit()
    db.refresh(row)
    return row


def delete_fact(db: Session, fact_id: int) -> None:
    row = db.get(TacticFact, fact_id)
    if row is not None:
        db.delete(row)
        db.commit()


def save_answers(db: Session, payload: schemas.AnswersIn) -> schemas.FactsOut:
    """Interview answers become facts verbatim ("Q — A": transparent and
    hand-editable). subject 'me' rows are global — never re-asked."""
    for item in payload.items:
        if not item.answer.strip():
            continue  # unanswered questions are simply skipped
        db.add(
            TacticFact(
                player_id=None if item.subject == "me" else payload.player_id,
                kind=item.kind,
                text=f"{item.question.strip()} — {item.answer.strip()}",
                source="interview",
            )
        )
    db.commit()
    return list_facts(db, payload.player_id)


# ------------------------------------------------------------------ reflections
def list_reflections(db: Session, player_id: int) -> list[schemas.ReflectionOut]:
    """Newest first — recent impressions override older ones, in the GUI and
    in the prompt alike."""
    rows = (
        db.query(TacticReflection)
        .filter(TacticReflection.player_id == player_id)
        .order_by(TacticReflection.id.desc())
        .all()
    )
    return [schemas.ReflectionOut.model_validate(r) for r in rows]


def add_reflection(db: Session, payload: schemas.ReflectionIn) -> TacticReflection:
    if db.get(Player, payload.player_id) is None:
        raise LookupError("Player not found")
    row = TacticReflection(player_id=payload.player_id, text=payload.text)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_reflection(
    db: Session, reflection_id: int, payload: schemas.ReflectionUpdate
) -> TacticReflection:
    row = db.get(TacticReflection, reflection_id)
    if row is None:
        raise LookupError("Reflection not found")
    text = payload.text.strip()
    if not text:
        raise ValueError("Reflection text cannot be empty.")
    row.text = text
    db.commit()
    db.refresh(row)
    return row


def delete_reflection(db: Session, reflection_id: int) -> None:
    row = db.get(TacticReflection, reflection_id)
    if row is not None:
        db.delete(row)
        db.commit()


# Auto-extraction never floods the me-file from one note.
_EXTRACT_MAX_FACTS = 5


def run_me_extraction_job(reflection_id: int, db_or_none: Session | None = None) -> None:
    """Background pass after a reflection is saved: the coach reads the note
    and files what it reveals about the STUDENT into the global me-file
    (source='coach' — the GUI marks these so the user can prune). Guards:
    only player_id NULL rows are ever written, exact-duplicate texts are
    skipped, and ANY failure is swallowed (the reflection itself was already
    saved — extraction is best-effort)."""
    db = db_or_none or SessionLocal()
    try:
        row = db.get(TacticReflection, reflection_id)
        if row is None:
            return
        opponent = db.get(Player, row.player_id)
        me_facts = (
            db.query(TacticFact)
            .filter(TacticFact.player_id.is_(None))
            .order_by(TacticFact.id)
            .all()
        )
        user_text = (
            f"=== HỒ SƠ HỌC TRÒ ĐÃ CÓ (KHÔNG lặp lại) ===\n"
            f"{_fact_lines(me_facts)}\n\n"
            f"=== GHI CHÚ MỚI CỦA HỌC TRÒ (về các trận với "
            f"{opponent.name if opponent else 'đối thủ'}) ===\n"
            f"{row.text}\n\n"
            f"Lọc ra những điều ghi chú tiết lộ về CHÍNH HỌC TRÒ theo LUẬT "
            f"trong system prompt (rỗng nếu không có gì mới)."
        )
        data = _ollama_chat(
            resolve_model(),
            [
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            EXTRACT_RESPONSE_SCHEMA,
            temperature=0.2,
            tag="tactics me-extraction",
        )
        existing = {f.text.strip().lower() for f in me_facts}
        added = 0
        for item in data.get("facts", [])[:_EXTRACT_MAX_FACTS]:
            text = str(item.get("text", "")).strip()
            if not text or text.lower() in existing:
                continue
            kind = item.get("kind")
            db.add(TacticFact(
                player_id=None,
                kind=kind if kind in FACT_KINDS else "note",
                text=text,
                source="coach",
            ))
            existing.add(text.lower())
            added += 1
        if added:
            db.commit()
            log.info("tactics me-extraction(%d): saved %d fact(s)", reflection_id, added)
    except Exception:  # noqa: BLE001 — best-effort; the note itself is safe
        db.rollback()
        log.warning("tactics me-extraction(%d) failed", reflection_id, exc_info=True)
    finally:
        if db_or_none is None:
            db.close()


# ------------------------------------------------------------- prompt context
def _h2h_matches(db: Session, player_id: int) -> list[Match]:
    """Every SINGLES match against this person, oldest first (the prompt
    reads old → new progressions). Doubles/1v2/2v1 are excluded — the plan
    is for the singles matchup."""
    return (
        db.query(Match)
        .filter(
            Match.is_nonplaying == False,  # noqa: E712
            Match.discipline == "singles",
            Match.opponent_id == player_id,
        )
        .order_by(Match.date, Match.order_index, Match.id)
        .all()
    )


def _match_line(m: Match) -> str:
    if m.my_sets == m.opp_sets:
        res = f"chưa có tỷ số ({m.my_sets}-{m.opp_sets})"
    else:
        res = f"{'THẮNG' if m.my_sets > m.opp_sets else 'THUA'} {m.my_sets}-{m.opp_sets}"
    parts = [
        m.date.isoformat(),
        res,
        _hdc_vi(m.handicap, m.handicap_pattern),
    ]
    if m.round:
        parts.append("vòng bảng" if m.round == "group" else _ROUND_NAME.get(m.round, m.round))
    if m.event is not None:
        parts.append(m.event.name)
    # Per-match journal note (2026-08-21) — the student's own read of that
    # exact match; gold scouting input.
    if m.note:
        parts.append(f"ghi chú của học trò: {m.note}")
    return "  - " + " · ".join(parts)


def _h2h_block(matches: list[Match]) -> str:
    decided = [m for m in matches if m.my_sets != m.opp_sets]
    wins = sum(1 for m in decided if m.my_sets > m.opp_sets)
    losses = len(decided) - wins
    by_hdc: dict[str, list[int]] = {}
    for m in decided:
        key = _hdc_vi(m.handicap, m.handicap_pattern)
        wl = by_hdc.setdefault(key, [0, 0])
        wl[0 if m.my_sets > m.opp_sets else 1] += 1
    hdc_lines = "; ".join(f"{k}: {w}W-{l}L" for k, (w, l) in by_hdc.items()) or "(chưa có)"
    shown = matches[-_H2H_PROMPT_LINES:]
    lines = "\n".join(_match_line(m) for m in shown) or "  (chưa có trận nào)"
    header = f"Tổng đối đầu: {wins}W-{losses}L ({len(matches)} trận). Theo kèo: {hdc_lines}."
    if len(matches) > len(shown):
        header += f" (liệt kê {len(shown)} trận gần nhất)"
    return f"{header}\n{lines}"


def _fact_lines(facts: list[TacticFact]) -> str:
    return "\n".join(
        f"  - [{_KIND_VI.get(f.kind, f.kind)}] {f.text}" for f in facts
    ) or "  (chưa có gì)"


def build_context(db: Session, player: Player) -> str:
    """The full Vietnamese context block both tactic prompts read."""
    matches = _h2h_matches(db, player.id)
    facts = (
        db.query(TacticFact)
        .filter(or_(TacticFact.player_id.is_(None), TacticFact.player_id == player.id))
        .order_by(TacticFact.id)
        .all()
    )
    me_facts = [f for f in facts if f.player_id is None]
    opp_facts = [f for f in facts if f.player_id is not None]
    reflections = list_reflections(db, player.id)  # newest first
    reflection_lines = "\n".join(
        f"  - [{r.created_at.date().isoformat() if r.created_at else '?'}] {r.text}"
        for r in reflections
    ) or "  (chưa có)"
    rating = compute_my_rating(db)
    pips = " Đánh GAI (mặt vợt gai)." if player.plays_pips else ""
    note = f" Ghi chú database: {player.note}." if player.note else ""
    points = f"{player.points} điểm BBTV" if player.points is not None else "chưa có điểm"
    coach_notes = "\n".join(
        f"  - {n['text']}" for n in _coach_note_dicts(db)
    ) or "  (chưa có)"
    return (
        f"=== ĐỐI THỦ ===\n"
        f"{player.name}: {points}.{pips}{note}\n\n"
        f"=== HỌC TRÒ (điểm hiện tại) ===\n"
        f"ELO động: {rating.current} (mốc tĩnh {rating.points}).\n\n"
        f"=== LỊCH SỬ ĐỐI ĐẦU TRẬN ĐƠN (cũ → mới; đôi/1v2/2v1 không tính) ===\n"
        f"CHÚ GIẢI KÈO — đọc đúng CHIỀU: 'được chấp N' = ĐỐI THỦ chấp HỌC TRÒ "
        f"N điểm/set (học trò cửa dưới, được cộng điểm trước); 'chấp N' = HỌC "
        f"TRÒ chấp đối thủ N điểm (học trò cửa trên); 'đồng' = không chấp. Khi "
        f"viết phải dùng ĐÚNG các cụm này — cấm tự đổi sang 'bị chấp' hay cách "
        f"nói khác làm đảo chiều kèo.\n"
        f"KÈO DẠNG CHUỖI 'X-Y-Z' (ví dụ '2-0-2') = mức chấp THEO TỪNG SET: "
        f"set 1 chấp X điểm, set 2 chấp Y, set 3 chấp Z. 'được chấp 2-0-2' và "
        f"'được chấp 2' là HAI KÈO KHÁC NHAU (2-0-2 nhẹ hơn nhiều) — TUYỆT "
        f"ĐỐI không rút gọn chuỗi thành một số, không gộp hai kèo khi so kết "
        f"quả; luôn trích nguyên văn cả chuỗi.\n"
        f"{_h2h_block(matches)}\n\n"
        f"=== HỒ SƠ SCOUTING VỀ HỌC TRÒ (đã lưu — KHÔNG hỏi lại) ===\n"
        f"{_fact_lines(me_facts)}\n\n"
        f"=== HỒ SƠ SCOUTING VỀ {player.name.upper()} (đã lưu) ===\n"
        f"{_fact_lines(opp_facts)}\n\n"
        f"=== PHÂN TÍCH CỦA HỌC TRÒ SAU CÁC TRẬN VỚI {player.name.upper()} "
        f"(mới nhất trước — CHỦ QUAN, phải đối chiếu với dữ liệu) ===\n"
        f"{reflection_lines}\n\n"
        f"=== SỔ TAY HLV (bối cảnh chung) ===\n"
        f"{coach_notes}\n"
    )


# ------------------------------------------------------------------- interview
def _interview_extras(db: Session, player_id: int) -> str:
    """Interview-only context: which fixed intake slots are still blank (the
    FORM collects those — the LLM must not burn questions on them) and the
    data_gaps the latest finished plan complained about (prime targets)."""
    keyed = {
        (f.player_id is None, f.key)
        for f in db.query(TacticFact)
        .filter(
            or_(TacticFact.player_id.is_(None), TacticFact.player_id == player_id),
            TacticFact.key.isnot(None),
        )
        .all()
    }
    missing_me = [v for k, v in ME_INTAKE_KEYS.items() if (True, k) not in keyed]
    missing_opp = [v for k, v in OPP_INTAKE_KEYS.items() if (False, k) not in keyed]
    last_plan = (
        db.query(TacticPlan)
        .filter(TacticPlan.player_id == player_id, TacticPlan.status == "done")
        .order_by(TacticPlan.id.desc())
        .first()
    )
    gaps = json.loads(last_plan.data_gaps_json) if last_plan else []
    lines = [
        "=== MỤC FORM CÒN TRỐNG (form trong app sẽ thu — KHÔNG hỏi, trừ ngoại lệ "
        "1 câu về đối thủ nếu quyết định trận đấu) ===",
        f"Về học trò: {', '.join(missing_me) or '(đủ cả)'}.",
        f"Về đối thủ: {', '.join(missing_opp) or '(đủ cả)'}.",
    ]
    if gaps:
        lines += [
            "=== GIÁO ÁN GẦN NHẤT CÒN THIẾU (data_gaps — ưu tiên hỏi) ===",
            *(f"  - {g}" for g in gaps),
        ]
    return "\n".join(lines)


def run_interview(db: Session, player_id: int) -> schemas.InterviewOut:
    """Synchronous structured-output call: the coach reads everything known
    and asks only for what's missing. Slow-ish (local LLM) but small — the
    button shows a spinner; no job row needed."""
    player = db.get(Player, player_id)
    if player is None:
        raise LookupError("Player not found")
    model = resolve_model()
    user_text = (
        f"{build_context(db, player)}\n"
        f"{_interview_extras(db, player_id)}\n\n"
        f"Học trò sắp đấu {player.name}. Hãy đặt câu hỏi scouting theo đúng "
        "LUẬT trong system prompt (tối đa 5, không hỏi lại điều đã lưu)."
    )
    data = _ollama_chat(
        model,
        [
            {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        INTERVIEW_RESPONSE_SCHEMA,
        temperature=0.4,
        tag="tactics interview",
    )
    questions = []
    for q in data.get("questions", [])[:5]:
        try:
            questions.append(schemas.InterviewQuestion(**q))
        except Exception:  # noqa: BLE001 — drop malformed items, keep the rest
            log.warning("tactics interview: dropped malformed question %r", q)
    return schemas.InterviewOut(model=model, questions=questions)


# ------------------------------------------------------------------- game plan
def _plan_out(row: TacticPlan) -> schemas.PlanOut:
    return schemas.PlanOut(
        id=row.id,
        created_at=row.created_at,
        player_id=row.player_id,
        model=row.model,
        status=row.status or "done",
        error_msg=row.error_msg,
        headline=row.headline,
        overall=row.overall,
        serve_receive=json.loads(row.serve_receive_json),
        rally=json.loads(row.rally_json),
        avoid=json.loads(row.avoid_json),
        mental=json.loads(row.mental_json),
        data_gaps=json.loads(row.data_gaps_json),
    )


def get_plan(db: Session, player_id: int) -> schemas.PlanOut:
    """The newest plan row for this opponent regardless of status (the GUI
    polls this while `generating`), or an `empty` placeholder."""
    row = (
        db.query(TacticPlan)
        .filter(TacticPlan.player_id == player_id)
        .order_by(TacticPlan.id.desc())
        .first()
    )
    return _plan_out(row) if row else schemas.PlanOut(player_id=player_id)


def start_plan(db: Session, player_id: int) -> schemas.PlanOut:
    """Create the `generating` placeholder (the heavy call runs in
    run_plan_job on a background task). One in-flight plan per opponent."""
    if db.get(Player, player_id) is None:
        raise LookupError("Player not found")
    running = (
        db.query(TacticPlan)
        .filter(TacticPlan.player_id == player_id, TacticPlan.status == "generating")
        .first()
    )
    if running is not None:
        raise ValueError("Đang lên giáo án cho đối thủ này — chờ xong rồi bấm lại.")
    row = TacticPlan(player_id=player_id, status="generating")
    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_out(row)


def run_plan_job(plan_id: int, db_or_none: Session | None = None) -> None:
    """Background job: build the context, call the model, fill the snapshot.
    Injected session = tests run it synchronously (head-coach job contract)."""
    db = db_or_none or SessionLocal()
    try:
        row = db.get(TacticPlan, plan_id)
        if row is None or row.status != "generating":
            return
        try:
            player = db.get(Player, row.player_id)
            if player is None:
                raise LookupError("Player not found")
            context = build_context(db, player)
            model = resolve_model()
            row.model = model
            user_text = (
                f"{context}\n"
                f"Hãy viết giáo án thi đấu để học trò THẮNG {player.name}, đúng "
                "JSON schema (tiếng Việt)."
            )
            data = _ollama_chat(
                model,
                [
                    {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                PLAN_RESPONSE_SCHEMA,
                temperature=0.3,
                tag="tactics plan",
            )
            if not (data.get("overall") or "").strip():
                raise ValueError("Model trả về giáo án rỗng.")
            # Persistence stays inside the try — a failure must mark the row
            # `error`, never leave it stuck `generating` with no job alive.
            row.headline = data.get("headline", "")
            row.overall = data.get("overall", "")
            row.serve_receive_json = json.dumps(data.get("serve_receive", []), ensure_ascii=False)
            row.rally_json = json.dumps(data.get("rally", []), ensure_ascii=False)
            row.avoid_json = json.dumps(data.get("avoid", []), ensure_ascii=False)
            row.mental_json = json.dumps(data.get("mental", []), ensure_ascii=False)
            row.data_gaps_json = json.dumps(data.get("data_gaps", []), ensure_ascii=False)
            row.sources_json = json.dumps({"context": context}, ensure_ascii=False)
            row.status = "done"
            row.error_msg = None
            db.commit()
        except Exception as exc:  # noqa: BLE001 — surfaced to the GUI via status
            log.exception("tactics plan(%d) failed", plan_id)
            db.rollback()
            row = db.get(TacticPlan, plan_id)
            if row is not None:
                row.status = "error"
                row.error_msg = str(exc)[:1000]
                db.commit()
    finally:
        if db_or_none is None:
            db.close()


def recover_stuck_plans(db: Session) -> None:
    """Startup: background jobs die with the process — a plan left
    `generating` would block its opponent's Generate button forever."""
    stuck = db.query(TacticPlan).filter(TacticPlan.status == "generating").all()
    for row in stuck:
        row.status = "error"
        row.error_msg = "Server restarted trong lúc đang chạy — bấm chạy lại."
    if stuck:
        log.warning("tactics: recovered %d stuck plan(s)", len(stuck))
        db.commit()
