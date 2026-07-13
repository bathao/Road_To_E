"""Coach chat + notebook: verbatim DB memory, auto-written notes, guardrails."""
from __future__ import annotations

import pytest

from app.features.head_coach import service as hc_service
from app.features.head_coach.models import CoachChatMessage, CoachNote


@pytest.fixture()
def fake_model(monkeypatch):
    """Stub the Ollama call: no network, deterministic reply + notes."""
    calls: list[dict] = []

    def _fake(context_text, history, question, model):
        calls.append(
            {
                "context": context_text,
                "history": history,
                "question": question,
                "model": model,
            }
        )
        return {
            "reply": "Còn 20 ngày tới giải. Đánh 4 trận đơn/tuần với người ngang cơ.",
            "new_notes": [
                "Mục tiêu: đánh đơn tốt cho giải ngày 2/8.",
                "",  # blank → skipped
            ],
        }

    monkeypatch.setattr(hc_service, "_call_chat_model", _fake)
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")
    return calls


def test_chat_reply_and_auto_notes(db, fake_model):
    hc_service.start_chat(db, "Tôi muốn đánh đơn tốt cho giải 2/8.")
    hc_service.run_chat_job(db)

    out = hc_service.chat_history(db)
    assert not out.pending
    assert [m.role for m in out.messages] == ["user", "coach"]
    coach = out.messages[-1]
    assert coach.status == "done" and "4 trận đơn" in coach.content
    assert coach.model == "test-model"

    # The note was auto-saved (no confirmation step, per the user's choice)
    # and the blank one was skipped.
    notes = hc_service.list_notes(db).notes
    assert [n.text for n in notes] == ["Mục tiêu: đánh đơn tốt cho giải ngày 2/8."]
    assert notes[0].source == "chat"

    # The model was grounded: bundle facts + the question it must answer.
    call = fake_model[-1]
    assert "SỔ TAY HLV" in call["context"]
    assert call["question"] == "Tôi muốn đánh đơn tốt cho giải 2/8."
    assert call["history"] == []  # first exchange → no prior turns


def test_second_turn_gets_history_and_notes_dedup(db, fake_model):
    hc_service.start_chat(db, "Tôi muốn đánh đơn tốt cho giải 2/8.")
    hc_service.run_chat_job(db)
    hc_service.start_chat(db, "Tuần này tôi bận, giảm được không?")
    hc_service.run_chat_job(db)

    # The first exchange is replayed verbatim as history.
    call = fake_model[-1]
    assert [m["role"] for m in call["history"]] == ["user", "assistant"]
    assert call["history"][0]["content"] == "Tôi muốn đánh đơn tốt cho giải 2/8."

    # The notebook (goal from turn 1) is injected into the grounding context…
    assert "giải ngày 2/8" in call["context"]
    # …and the identical note suggested again is NOT duplicated.
    assert db.query(CoachNote).count() == 1


def test_one_question_at_a_time(db):
    hc_service.start_chat(db, "Câu hỏi 1")
    with pytest.raises(ValueError):
        hc_service.start_chat(db, "Câu hỏi 2")


def test_model_failure_marks_error_not_lost(db, monkeypatch):
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")

    def _boom(*_a, **_k):
        raise RuntimeError("Ollama down")

    monkeypatch.setattr(hc_service, "_call_chat_model", _boom)
    hc_service.start_chat(db, "Câu hỏi")
    hc_service.run_chat_job(db)

    out = hc_service.chat_history(db)
    coach = out.messages[-1]
    assert coach.status == "error" and "Ollama down" in (coach.error_msg or "")
    assert not out.pending  # the player can ask again
    # The user's question itself is never lost.
    assert out.messages[0].content == "Câu hỏi"


def test_empty_reply_retried_once(db, monkeypatch):
    """First structured-output call after model load can come back empty
    (seen in smoke tests) — the job retries once before reporting an error."""
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")
    attempts: list[int] = []

    def _flaky(*_a, **_k):
        attempts.append(1)
        if len(attempts) == 1:
            return {"reply": "", "new_notes": []}
        return {"reply": "Trả lời được rồi.", "new_notes": []}

    monkeypatch.setattr(hc_service, "_call_chat_model", _flaky)
    hc_service.start_chat(db, "Câu hỏi")
    hc_service.run_chat_job(db)

    coach = hc_service.chat_history(db).messages[-1]
    assert len(attempts) == 2
    assert coach.status == "done" and coach.content == "Trả lời được rồi."


def test_notebook_add_delete_and_verdict_bundle(db):
    hc_service.add_note(db, "Tuần 14-20/7 đi công tác, giảm khối lượng.")
    notes = hc_service.list_notes(db).notes
    assert len(notes) == 1 and notes[0].source == "user"

    # The notebook feeds the weekly verdict bundle too.
    bundle = hc_service.gather_bundle(db)
    assert any("công tác" in n["text"] for n in bundle.coach_notes)
    assert "công tác" in hc_service._bundle_to_text(bundle)

    hc_service.delete_note(db, notes[0].id)
    assert hc_service.list_notes(db).notes == []


def test_chat_api_flow(client, db, monkeypatch):
    # The background job must not touch the real DB from a test.
    monkeypatch.setattr(hc_service, "run_chat_job", lambda *a, **k: None)

    r = client.post("/api/head-coach/chat", json={"text": "Chào HLV"})
    assert r.status_code == 200
    body = r.json()
    assert body["pending"] is True
    assert [m["role"] for m in body["messages"]] == ["user", "coach"]

    # A second question while one is in flight is refused.
    r2 = client.post("/api/head-coach/chat", json={"text": "Nữa"})
    assert r2.status_code == 409

    r3 = client.get("/api/head-coach/chat")
    assert r3.status_code == 200 and r3.json()["pending"] is True


def test_debug_endpoint(client, monkeypatch):
    """The dev panel endpoint always renders: log tail + Ollama state (here:
    unreachable), no DB involved."""
    import logging

    from app.core import logbuffer

    logbuffer.install()
    # warning: under pytest the root level may still be WARNING (basicConfig
    # in app.main is a no-op once pytest installed its own handlers).
    logging.getLogger("app.test").warning("hello from the ring buffer")

    def _no_ollama(*_a, **_k):
        raise ConnectionError("refused")

    monkeypatch.setattr(hc_service.httpx, "get", _no_ollama)
    r = client.get("/api/head-coach/debug")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama_ok"] is False and "refused" in body["ollama_error"]
    assert any("hello from the ring buffer" in line for line in body["logs"])


def test_history_budget_keeps_newest(db):
    rows = [
        CoachChatMessage(role="user", content="x" * 5000, status="done"),
        CoachChatMessage(role="coach", content="y" * 5000, status="done"),
        CoachChatMessage(role="user", content="câu mới nhất", status="done"),
    ]
    for r in rows:
        db.add(r)
    db.commit()
    picked = hc_service._history_for_prompt(
        db.query(CoachChatMessage).order_by(CoachChatMessage.id.asc()).all()
    )
    # Newest messages survive the budget; the oldest 5k blob is dropped.
    assert picked[-1]["content"] == "câu mới nhất"
    assert len(picked) == 2
