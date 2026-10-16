"""The verdict: start/run the generation job, read the latest snapshot, sanitise directives.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.core.settings import HEAD_COACH_MODEL
from app.features.head_coach import schemas
from app.features.head_coach.models import (
    HeadCoachAssessment,
)
from app.features.head_coach.prompt import (
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
)
from app.shared.jobs import run_llm_job
from app.shared.ollama import (
    resolve_model,
)

from .bundle import gather_bundle
from .common import _call_with_empty_retry, _ollama_chat, _tz
from .render import _bundle_to_text

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- synthesise
def _call_model(context_text: str, player_name: str, model: str) -> dict:
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
        "- week_plan: kế hoạch cho ĐÚNG 7 NGÀY TỚI theo mục '7 NGÀY TỚI' trong "
        "dữ liệu — đúng 7 mục, đúng thứ tự; 'day' phải COPY NGUYÊN VĂN nhãn "
        "ngày đã cấp (ví dụ 'Thứ 6 15/08'), KHÔNG tự bịa thứ/ngày khác. Ngày "
        "nào được ghi có giải thì focus/detail phải phục vụ đúng giải đó (thi "
        "đấu, hoặc giảm khối lượng 1-2 ngày sát giải); KHÔNG nhắc tới ngày hay "
        "giải không có trong dữ liệu. Mỗi ngày có focus + detail gắn với tập "
        "thể lực và loại trận cần đánh; nhớ giới hạn an toàn đầu gối.\n"
        "- watch_items: cảnh báo (dữ liệu mỏng/cũ, an toàn, điều cần theo dõi)."
    )
    return _ollama_chat(
        model,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        RESPONSE_SCHEMA,
        temperature=0.3,
        tag="head coach",
    )


def start_generate(db: Session) -> schemas.AssessmentOut:
    """Create a `generating` placeholder row; the heavy work (gather + local
    LLM, up to minutes) runs in run_generate_job on a background task. The
    UI polls GET /status until the status leaves `generating`.

    Refuses while one is already running (same guard as chat/recap — review
    find 2026-08-09: a double click spawned two concurrent Ollama calls and
    the older row stayed `generating` invisibly)."""
    running = (
        db.query(HeadCoachAssessment)
        .filter(HeadCoachAssessment.status == "generating")
        .first()
    )
    if running is not None:
        raise Conflict("Đang tạo nhận định — chờ xong rồi bấm lại.")
    row = HeadCoachAssessment(model=HEAD_COACH_MODEL, status="generating")
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def run_generate_job(assessment_id: int, db_or_none: Session | None = None) -> None:
    """Background job: gather the bundle, call the model, fill the snapshot.
    Accepts an injected session so tests can run it synchronously (same
    contract as run_chat_job / run_recap_job)."""

    def work(db: Session, row: HeadCoachAssessment) -> None:
        bundle = gather_bundle(db)
        use_model = resolve_model()
        row.model = use_model  # record the model actually used

        def call() -> dict:
            return _call_model(
                _bundle_to_text(bundle),
                player_name=bundle.player or "vận động viên",
                model=use_model,
            )

        data = _call_with_empty_retry(call, "overall_assessment", "head coach", use_model)
        if not (data.get("overall_assessment") or "").strip():
            raise ValueError("Model trả về bản đánh giá rỗng.")
        row.overall_assessment = data.get("overall_assessment", "")
        row.top_priorities_json = json.dumps(data.get("top_priorities", []), ensure_ascii=False)
        row.directives_json = json.dumps(
            _sanitize_directives(data.get("directives", [])), ensure_ascii=False
        )
        row.week_plan_json = json.dumps(data.get("week_plan", []), ensure_ascii=False)
        row.watch_items_json = json.dumps(data.get("watch_items", []), ensure_ascii=False)
        row.sources_json = bundle.model_dump_json()
        row.status = "done"
        row.error_msg = None

    run_llm_job(
        db_or_none,
        fetch=lambda db: db.get(HeadCoachAssessment, assessment_id),
        work=work,
        tag=f"head coach generate({assessment_id})",
    )


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


# ------------------------------------------------- directive live progress
# Plausible weekly ranges per metric. A model-filled value outside its range is
# nonsense (e.g. "240 coach hours/week") → the metric tag is dropped and the
# directive stays text-only.
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
