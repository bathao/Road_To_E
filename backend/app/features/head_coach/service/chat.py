"""Grounded coach chat: history, pending reply job, auto-written notes.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.features.head_coach import schemas
from app.features.head_coach.models import (
    CoachChatMessage,
    CoachNote,
)
from app.features.head_coach.prompt import (
    CHAT_RESPONSE_SCHEMA,
    CHAT_SYSTEM_PROMPT,
)
from app.shared.jobs import run_llm_job
from app.shared.ollama import (
    resolve_model,
)

from .bundle import gather_bundle
from .common import _call_with_empty_retry, _ollama_chat, _tz
from .render import _bundle_to_text

# ------------------------------------------------------------------ coach chat
# Char budget for the verbatim history injected per reply. The FULL history
# always lives in the DB; this only bounds what goes into one model call
# (~8k chars of chat + ~3k bundle fits far inside num_ctx=16384). At the
# user's current volume this truncates nothing for a very long time.
_CHAT_HISTORY_CHAR_BUDGET = 8000


# Guardrails on the auto-written notebook (per reply).
_MAX_NOTES_PER_REPLY = 3


_MAX_NOTE_CHARS = 300


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
        raise Conflict("HLV đang trả lời câu trước — chờ xong rồi gửi tiếp.")
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


def _pending_reply(db: Session) -> CoachChatMessage | None:
    return (
        db.query(CoachChatMessage)
        .filter(CoachChatMessage.status == "pending", CoachChatMessage.role == "coach")
        .order_by(CoachChatMessage.id.asc())
        .first()
    )


def run_chat_job(db_or_none: Session | None = None) -> None:
    """Background job: answer the oldest pending coach message.

    Injects the live bundle (with notebook) + the verbatim history from the
    DB, calls the model, saves the reply and auto-writes any new notes."""

    def work(db: Session, row: CoachChatMessage) -> None:
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
            return _call_chat_model(
                _bundle_to_text(bundle),
                history=_history_for_prompt(all_rows[:-1]),
                question=question_row.content,
                model=use_model,
            )

        data = _call_with_empty_retry(call, "reply", "coach chat", use_model)
        row.content = (data.get("reply") or "").strip()
        if not row.content:
            row.status = "error"
            row.error_msg = "Model trả về câu trả lời rỗng."
        else:
            row.status = "done"
            row.error_msg = None
            _save_new_notes(db, data.get("new_notes"))

    run_llm_job(db_or_none, fetch=_pending_reply, work=work, tag="coach chat reply",
                in_flight="pending")
