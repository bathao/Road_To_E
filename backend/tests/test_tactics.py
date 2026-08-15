"""Tactics tab: opponent picker, scouting facts (me-facts are global and
never re-asked), interview answers → facts, and the game-plan job."""
from __future__ import annotations

import datetime as dt
import json

import pytest

from conftest import category_id
from app.features.tactics import schemas, service
from app.features.tactics.models import TacticPlan
from app.features.tracker.models import Match, Player

D = dt.date(2026, 8, 1)


def _player(db, name, points=800):
    p = Player(name=name, level="equal", points=points)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _match(db, cat, *, opp=None, opp2=None, partner=None, my=3, o=1,
           date=D, handicap=0, pattern=None, order=0, discipline="singles"):
    db.add(Match(
        date=date, category_id=cat, discipline=discipline, best_of=5,
        my_sets=my, opp_sets=o, is_nonplaying=False, order_index=order,
        opponent_id=opp, opponent2_id=opp2, partner_id=partner,
        handicap=handicap, handicap_pattern=pattern,
    ))
    db.commit()


def test_opponents_list_is_singles_only(db):
    """The tab is SINGLES tactics (user 2026-08-15): doubles/1v2/2v1 matches
    never count, partner-only people never appear."""
    cat = category_id(db, "tournament_match")
    rival = _player(db, "Lợi Phạm")
    once = _player(db, "Tuấn Gỗ")
    buddy = _player(db, "Đồng Đội")  # partner-only → not an opponent

    _match(db, cat, opp=rival.id, my=0, o=3)
    _match(db, cat, opp=rival.id, my=3, o=2, date=D + dt.timedelta(days=5), order=1)
    _match(db, cat, opp=once.id, my=1, o=3, order=2)
    # Doubles vs the same rival — excluded from counts entirely.
    _match(db, cat, opp=rival.id, opp2=once.id, partner=buddy.id,
           my=3, o=0, discipline="doubles", order=3)

    out = service.list_opponents(db)
    assert [o.name for o in out] == ["Lợi Phạm", "Tuấn Gỗ"]
    top = out[0]
    assert (top.matches_vs, top.wins, top.losses) == (2, 1, 1)  # doubles win not counted
    assert top.last_vs == D + dt.timedelta(days=5)


def test_h2h_context_excludes_non_singles(db):
    cat = category_id(db, "tournament_match")
    rival = _player(db, "Lợi Phạm")
    _match(db, cat, opp=rival.id, my=0, o=3)
    _match(db, cat, opp=rival.id, my=3, o=1, discipline="doubles", order=1)
    ctx = service.build_context(db, db.get(Player, rival.id))
    assert "Tổng đối đầu: 0W-1L (1 trận)" in ctx  # the doubles win is invisible


def test_facts_crud_and_split(db):
    rival = _player(db, "Lợi Phạm")
    me_fact = service.add_fact(db, schemas.FactIn(player_id=None, kind="weakness",
                                                  text="Trái tay yếu khi bị ép dài"))
    service.add_fact(db, schemas.FactIn(player_id=rival.id, kind="style",
                                        text="Ôm bàn, đôi công nhanh"))

    facts = service.list_facts(db, rival.id)
    assert [f.text for f in facts.me] == ["Trái tay yếu khi bị ép dài"]
    assert [f.kind for f in facts.opponent] == ["style"]

    service.update_fact(db, me_fact.id, schemas.FactUpdate(text="Trái tay yếu"))
    assert service.list_facts(db, rival.id).me[0].text == "Trái tay yếu"
    with pytest.raises(ValueError):
        service.update_fact(db, me_fact.id, schemas.FactUpdate(text="   "))
    with pytest.raises(LookupError):
        service.update_fact(db, 999, schemas.FactUpdate(text="x"))

    service.delete_fact(db, me_fact.id)
    assert service.list_facts(db, rival.id).me == []


def test_interview_answers_become_facts(db):
    """'me' answers store globally (player_id NULL — the never-re-ask store);
    opponent answers pin to the opponent; blank answers are skipped."""
    rival = _player(db, "Lợi Phạm")
    out = service.save_answers(db, schemas.AnswersIn(player_id=rival.id, items=[
        schemas.AnswerIn(subject="me", kind="strength",
                         question="Quả nào anh tự tin nhất?", answer="Giật phải"),
        schemas.AnswerIn(subject="opponent", kind="weakness",
                         question="Đối thủ ngại xoáy gì?", answer="Xoáy xuống nặng"),
        schemas.AnswerIn(subject="opponent", kind="note",
                         question="Bỏ trống?", answer="   "),
    ]))
    assert [f.text for f in out.me] == ["Quả nào anh tự tin nhất? — Giật phải"]
    assert [f.source for f in out.me] == ["interview"]
    assert [f.text for f in out.opponent] == ["Đối thủ ngại xoáy gì? — Xoáy xuống nặng"]
    # The me-fact is visible from ANY other opponent's matchup view.
    other = _player(db, "Tuấn Gỗ")
    assert [f.text for f in service.list_facts(db, other.id).me] == [
        "Quả nào anh tự tin nhất? — Giật phải"
    ]


def test_build_context_includes_h2h_and_facts(db):
    cat = category_id(db, "tournament_match")
    rival = _player(db, "Lợi Phạm", points=900)
    _match(db, cat, opp=rival.id, my=0, o=3, handicap=-2)
    _match(db, cat, opp=rival.id, my=2, o=3, handicap=-2,
           date=D + dt.timedelta(days=7), order=1)
    service.add_fact(db, schemas.FactIn(player_id=None, kind="weakness", text="Trái tay yếu"))
    service.add_fact(db, schemas.FactIn(player_id=rival.id, kind="style", text="Đánh gai công"))

    ctx = service.build_context(db, db.get(Player, rival.id))
    assert "Tổng đối đầu: 0W-2L (2 trận)" in ctx
    assert "được chấp 2: 0W-2L" in ctx
    assert "THUA 2-3" in ctx
    assert "[Điểm yếu] Trái tay yếu" in ctx
    assert "[Lối đánh] Đánh gai công" in ctx
    assert "KHÔNG hỏi lại" in ctx  # the never-re-ask contract rides the prompt


def test_interview_parses_and_caps_questions(db, monkeypatch):
    rival = _player(db, "Lợi Phạm")
    canned = {"questions": (
        [{"subject": "opponent", "kind": "weakness", "question": f"Q{i}?"}
         for i in range(6)]  # 6 → capped to 5
        + [{"subject": "??", "bad": True}]  # malformed → dropped
    )}
    monkeypatch.setattr(service, "resolve_model", lambda: "test-model")
    monkeypatch.setattr(service, "_ollama_chat", lambda *a, **k: canned)

    out = service.run_interview(db, rival.id)
    assert out.model == "test-model"
    assert [q.question for q in out.questions] == [f"Q{i}?" for i in range(5)]
    with pytest.raises(LookupError):
        service.run_interview(db, 999)


def test_plan_job_lifecycle(db, monkeypatch):
    rival = _player(db, "Lợi Phạm")
    monkeypatch.setattr(service, "resolve_model", lambda: "test-model")
    monkeypatch.setattr(service, "_ollama_chat", lambda *a, **k: {
        "headline": "Ép trái, biến nhịp",
        "overall": "Anh thua chủ yếu vì đôi công thuận tay.",
        "serve_receive": ["Giao xoáy xuống ngắn vào trái"],
        "rally": ["Đổi nhịp sang trái sớm"],
        "avoid": ["Không đôi công thuận tay kèo dài"],
        "mental": ["9-9 chọn quả an toàn vào trái"],
        "data_gaps": ["Đối thủ đỡ giao xoáy ngang thế nào?"],
    })

    # No plan yet → empty placeholder.
    assert service.get_plan(db, rival.id).status == "empty"

    out = service.start_plan(db, rival.id)
    assert out.status == "generating"
    with pytest.raises(ValueError):  # one in-flight per opponent
        service.start_plan(db, rival.id)
    with pytest.raises(LookupError):
        service.start_plan(db, 999)

    service.run_plan_job(out.id, db)
    plan = service.get_plan(db, rival.id)
    assert plan.status == "done"
    assert plan.headline == "Ép trái, biến nhịp"
    assert plan.serve_receive == ["Giao xoáy xuống ngắn vào trái"]
    assert plan.data_gaps == ["Đối thủ đỡ giao xoáy ngang thế nào?"]
    row = db.get(TacticPlan, plan.id)
    assert "LỊCH SỬ ĐỐI ĐẦU" in json.loads(row.sources_json)["context"]

    # Empty model output → visible error, row never stuck.
    monkeypatch.setattr(service, "_ollama_chat", lambda *a, **k: {})
    out2 = service.start_plan(db, rival.id)
    service.run_plan_job(out2.id, db)
    assert service.get_plan(db, rival.id).status == "error"


def test_recover_stuck_plans(db):
    rival = _player(db, "Lợi Phạm")
    row = TacticPlan(player_id=rival.id, status="generating")
    db.add(row)
    db.commit()
    service.recover_stuck_plans(db)
    db.refresh(row)
    assert row.status == "error" and "restart" in (row.error_msg or "")
    # ...and the button works again.
    assert service.start_plan(db, rival.id).status == "generating"
