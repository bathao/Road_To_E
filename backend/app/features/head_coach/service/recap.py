"""Week / month recaps: start/run the job, read the latest.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict
from app.core.settings import HEAD_COACH_MODEL
from app.features.head_coach import schemas
from app.features.head_coach.models import (
    HeadCoachRecap,
)
from app.features.head_coach.prompt import (
    RECAP_RESPONSE_SCHEMA,
    RECAP_SYSTEM_PROMPT,
)
from app.features.tracker import rating as tracker_rating
from app.features.tracker import service as tracker_service
from app.shared.jobs import run_llm_job
from app.shared.ollama import (
    resolve_model,
)

from .bundle import (
    _RECAP_PERIODS,
    _RECAP_WINDOW_DAYS,
    _period_stats,
    gather_recap_bundle,
)
from .common import _call_with_empty_retry, _ollama_chat, _tz
from .render import _recap_bundle_to_text


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
        latest=_recap_to_out(latest_row) if latest_row is not None else None,
    )


def start_recap(
    db: Session, period_type: str, today: dt.date | None = None
) -> schemas.RecapOut:
    """Start generating a recap of the window ENDING TODAY (last 7/30 days,
    results up to the moment the button is pressed). Pressing again on the
    same day reuses that day's row (regenerate) — no duplicate rows."""
    today = today or dt.date.today()
    if period_type not in _RECAP_PERIODS:
        raise BadRequest("period_type must be 'week' or 'month'")
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
        raise Conflict("Đang tạo tổng kết — chờ xong rồi bấm lại.")
    if not tracker_service.has_data_between(db, start, today):
        raise BadRequest(f"Chưa có dữ liệu nào trong {days} ngày qua — không có gì để tổng kết.")

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

    def work(db: Session, row: HeadCoachRecap) -> None:
        rep = tracker_rating.replay(db)
        cur_snap, full_stats, elo = _period_stats(
            db, row.period_start, row.period_end, rep
        )
        # The comparison window: the same number of days right before.
        days = _RECAP_WINDOW_DAYS[row.period_type]
        prev_end = row.period_start - dt.timedelta(days=1)
        prev_start = prev_end - dt.timedelta(days=days - 1)
        earliest = tracker_service.earliest_data_date(db)
        prev_snap = None
        if earliest is not None and prev_end >= earliest:
            prev_snap, _, _ = _period_stats(db, prev_start, prev_end, rep)
        stats = schemas.RecapStats(current=cur_snap, previous=prev_snap)

        bundle = gather_recap_bundle(
            db, row.period_type, row.period_start, row.period_end,
            rep, stats, full_stats, elo,
        )
        use_model = resolve_model()
        row.model = use_model

        def call() -> dict:
            return _call_recap_model(
                _recap_bundle_to_text(bundle),
                player_name=bundle.get("player") or "vận động viên",
                period_type=row.period_type,
                model=use_model,
            )

        data = _call_with_empty_retry(call, "overall", "coach recap", use_model)
        if not (data.get("overall") or "").strip():
            raise ValueError("Model trả về bản tổng kết rỗng.")
        row.headline = (data.get("headline") or "").strip()
        row.overall = data.get("overall", "")
        row.went_well_json = json.dumps(data.get("went_well", []), ensure_ascii=False)
        row.concerns_json = json.dumps(data.get("concerns", []), ensure_ascii=False)
        row.focus_next_json = json.dumps(data.get("focus_next", []), ensure_ascii=False)
        row.stats_json = stats.model_dump_json()
        row.sources_json = json.dumps(bundle, ensure_ascii=False)
        row.status = "done"
        row.error_msg = None

    run_llm_job(
        db_or_none,
        fetch=lambda db: db.get(HeadCoachRecap, recap_id),
        work=work,
        tag=f"coach recap({recap_id})",
    )
