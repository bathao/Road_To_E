"""The shared layer (REFACTOR.md Phase 2): typed errors → HTTP codes, the
LLM job lifecycle, and the Ollama call's reply hygiene."""
from __future__ import annotations

import json

import pytest

from conftest import category_id
from app.core import errors
from app.features.head_coach.models import HeadCoachAssessment
from app.features.tracker.models import Player
from app.shared import jobs, ollama


# ---------------------------------------------------------------- errors
def test_typed_errors_subclass_the_builtins_they_replace():
    assert issubclass(errors.NotFound, LookupError)
    assert issubclass(errors.Conflict, ValueError)
    assert issubclass(errors.BadRequest, ValueError)
    assert (errors.NotFound.status_code, errors.Conflict.status_code,
            errors.BadRequest.status_code) == (404, 409, 400)


def test_error_handler_maps_codes_and_keeps_messages(client, db):
    # 404 — an id that does not exist (service message, not a router string).
    r = client.patch("/api/tracker/matches/999/note", json={"note": "x"})
    assert r.status_code == 404 and r.json()["detail"] == "match 999 not found"
    # 409 — valid payload, refused by the current state.
    client.post("/api/tracker/coaches", json={"name": "Coach X", "counts_package": True})
    r = client.post("/api/tracker/coaches", json={"name": "coach x", "counts_package": True})
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    db.add_all([Player(name="Anna", points=900), Player(name="Binh", points=900)])
    db.commit()
    binh = db.query(Player).filter(Player.name == "Binh").one()
    r = client.put(f"/api/tracker/players/{binh.id}", json={"name": "anna"})
    assert r.status_code == 409
    r = client.post("/api/tracker/coach-packages/start-next")
    assert r.status_code == 409
    # 400 — the payload itself is wrong for this operation.
    r = client.post("/api/tracker/session-notes", json={
        "date": "2026-06-01", "kind": "advice", "text": "x",
    })
    assert r.status_code == 400 and "Train with Coach" in r.json()["detail"]
    # Tactics / head coach answer the same way.
    assert client.get("/api/tactics/matchlog/999").status_code == 404
    assert client.put("/api/tactics/facts/999", json={"text": "x"}).status_code == 404
    category_id(db, "practice_match")  # the fixture DB is seeded — sanity


# ------------------------------------------------------------------ jobs
def test_run_llm_job_marks_row_error_on_failure_and_skips_settled_rows(db):
    row = HeadCoachAssessment(model="m", status="generating")
    db.add(row)
    db.commit()

    def boom(_db, _row):
        raise RuntimeError("ollama down")

    jobs.run_llm_job(db, fetch=lambda s: s.get(HeadCoachAssessment, row.id), work=boom, tag="t")
    db.refresh(row)
    assert row.status == "error" and row.error_msg == "ollama down"

    # A row that is no longer in flight is left alone.
    calls = []
    jobs.run_llm_job(db, fetch=lambda s: s.get(HeadCoachAssessment, row.id),
                     work=lambda *_: calls.append(1), tag="t")
    assert calls == []

    # Success path: work sets fields, the helper commits.
    row2 = HeadCoachAssessment(model="m", status="generating")
    db.add(row2)
    db.commit()

    def ok(_db, r):
        r.status = "done"
        r.overall_assessment = "fine"

    jobs.run_llm_job(db, fetch=lambda s: s.get(HeadCoachAssessment, row2.id), work=ok, tag="t")
    db.expire_all()
    assert db.get(HeadCoachAssessment, row2.id).status == "done"


def test_recover_stuck_flips_in_flight_rows(db):
    db.add_all([
        HeadCoachAssessment(model="m", status="generating"),
        HeadCoachAssessment(model="m", status="done"),
    ])
    db.commit()
    assert jobs.recover_stuck(db, HeadCoachAssessment, in_flight="generating", label="x") == 1
    db.commit()
    statuses = sorted(r.status for r in db.query(HeadCoachAssessment).all())
    assert statuses == ["done", "error"]
    err = db.query(HeadCoachAssessment).filter_by(status="error").one()
    assert err.error_msg == jobs.STUCK_MSG


# ---------------------------------------------------------------- ollama
class _Resp:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": self._content}}


@pytest.mark.parametrize("content,expected", [
    ('{"reply": "ok"}', {"reply": "ok"}),
    ("", {}),             # empty reply → {} (the callers' empty check handles it)
    ("[1, 2]", {}),       # non-object JSON → {}
])
def test_ollama_chat_always_returns_a_dict(monkeypatch, content, expected):
    monkeypatch.setattr(ollama.httpx, "post", lambda *a, **k: _Resp(content))
    out = ollama.ollama_chat("m", [], {}, temperature=0.1, tag="t")
    assert out == expected


def test_ollama_chat_invalid_json_is_a_readable_error(monkeypatch):
    monkeypatch.setattr(ollama.httpx, "post", lambda *a, **k: _Resp("{not json"))
    with pytest.raises(ValueError) as exc:
        ollama.ollama_chat("m", [], {}, temperature=0.1, tag="t")
    assert "JSON" in str(exc.value)
    assert isinstance(exc.value.__cause__, json.JSONDecodeError)


def test_ollama_chat_payload_shape(monkeypatch):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen.update(url=url, json=json, timeout=timeout)
        return _Resp("{}")

    monkeypatch.setattr(ollama.httpx, "post", fake_post)
    ollama.ollama_chat("qwen", [{"role": "user", "content": "hi"}], {"type": "object"},
                       temperature=0.3, tag="t")
    assert seen["url"].endswith("/api/chat") and seen["timeout"] == ollama.CHAT_TIMEOUT_S
    assert seen["json"]["model"] == "qwen" and seen["json"]["stream"] is False
    assert seen["json"]["format"] == {"type": "object"}
    assert seen["json"]["options"] == {"temperature": 0.3, "num_ctx": ollama.NUM_CTX}
