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


def test_intake_facts_upsert_by_key(db):
    """Keyed (intake) facts: one row per (player_id, key) — re-answering
    edits in place; the same key on me vs an opponent (or two opponents)
    never collides."""
    rival = _player(db, "Lợi Phạm")
    other = _player(db, "Tuấn Gỗ")

    first = service.add_fact(db, schemas.FactIn(
        player_id=None, kind="style", key="grip", text="Grip: Shakehand (vợt ngang)"))
    assert (first.source, first.key) == ("intake", "grip")

    # Same key again → the row is updated, not duplicated.
    second = service.add_fact(db, schemas.FactIn(
        player_id=None, kind="style", key="grip", text="Grip: Penhold (vợt dọc)"))
    assert second.id == first.id
    me = service.list_facts(db, rival.id).me
    assert [(f.key, f.text) for f in me] == [("grip", "Grip: Penhold (vợt dọc)")]

    # No cross-talk: me / rival / other each own their 'grip' slot.
    service.add_fact(db, schemas.FactIn(
        player_id=rival.id, kind="style", key="grip", text="Grip: Shakehand"))
    service.add_fact(db, schemas.FactIn(
        player_id=other.id, kind="style", key="grip", text="Grip: Penhold"))
    assert [f.text for f in service.list_facts(db, rival.id).opponent] == ["Grip: Shakehand"]
    assert [f.text for f in service.list_facts(db, other.id).opponent] == ["Grip: Penhold"]

    # Free-form facts still append (no upsert without a key).
    service.add_fact(db, schemas.FactIn(player_id=None, kind="note", text="A"))
    service.add_fact(db, schemas.FactIn(player_id=None, kind="note", text="A"))
    assert len(service.list_facts(db, rival.id).me) == 3


def test_interview_context_lists_missing_intake_and_plan_gaps(db, monkeypatch):
    """The interview user-text tells the model which fixed intake slots are
    still blank (the form collects those) and feeds the latest plan's
    data_gaps back as priority questions."""
    rival = _player(db, "Lợi Phạm")
    seen: dict = {}

    def fake_chat(model, messages, schema, **kw):
        seen["user"] = messages[1]["content"]
        return {"questions": []}

    monkeypatch.setattr(service, "resolve_model", lambda: "test-model")
    monkeypatch.setattr(service, "_ollama_chat", fake_chat)

    service.run_interview(db, rival.id)
    assert "MỤC FORM CÒN TRỐNG" in seen["user"]
    assert "cầm vợt dọc/ngang" in seen["user"]  # everything is missing at first
    assert "GIÁO ÁN GẦN NHẤT" not in seen["user"]  # no plan yet → no gaps block

    # Answer one me-slot and one rival-slot → both leave the missing lists.
    service.add_fact(db, schemas.FactIn(
        player_id=None, kind="style", key="grip", text="Grip: Shakehand"))
    service.add_fact(db, schemas.FactIn(
        player_id=rival.id, kind="note", key="clutch", text="At 8-8 / 9-9: Gets shaky"))
    service.run_interview(db, rival.id)
    me_line = next(l for l in seen["user"].splitlines() if l.startswith("Về học trò"))
    opp_line = next(l for l in seen["user"].splitlines() if l.startswith("Về đối thủ"))
    assert "cầm vợt" not in me_line and "tay thuận" in me_line
    assert "tâm lý điểm căng" not in opp_line and "tay thuận" in opp_line

    # A finished plan's data_gaps ride the next interview.
    row = TacticPlan(player_id=rival.id, status="done",
                     data_gaps_json=json.dumps(["Đối thủ đỡ xoáy ngang thế nào?"],
                                               ensure_ascii=False))
    db.add(row)
    db.commit()
    service.run_interview(db, rival.id)
    assert "GIÁO ÁN GẦN NHẤT CÒN THIẾU" in seen["user"]
    assert "Đối thủ đỡ xoáy ngang thế nào?" in seen["user"]


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


def test_reflections_crud_newest_first(db):
    """The student's post-match analysis notes: per-opponent, newest first,
    blank guards, unknown-player 404."""
    rival = _player(db, "Lợi Phạm")
    other = _player(db, "Tuấn Gỗ")

    r1 = service.add_reflection(db, schemas.ReflectionIn(
        player_id=rival.id, text="Giao dài là hắn lùi ra xa, mình bị động."))
    service.add_reflection(db, schemas.ReflectionIn(
        player_id=rival.id, text="Hôm nay thử giao ngắn: hắn lúng túng."))
    service.add_reflection(db, schemas.ReflectionIn(
        player_id=other.id, text="Người khác — không được lẫn sang."))

    out = service.list_reflections(db, rival.id)
    assert [r.text for r in out] == [
        "Hôm nay thử giao ngắn: hắn lúng túng.",
        "Giao dài là hắn lùi ra xa, mình bị động.",
    ]  # newest first

    service.update_reflection(db, r1.id, schemas.ReflectionUpdate(
        text="Giao dài là hắn lùi xa."))
    assert service.list_reflections(db, rival.id)[-1].text == "Giao dài là hắn lùi xa."
    with pytest.raises(ValueError):
        service.update_reflection(db, r1.id, schemas.ReflectionUpdate(text="   "))
    with pytest.raises(LookupError):
        service.update_reflection(db, 999, schemas.ReflectionUpdate(text="x"))
    with pytest.raises(LookupError):
        service.add_reflection(db, schemas.ReflectionIn(player_id=999, text="x"))

    service.delete_reflection(db, r1.id)
    assert len(service.list_reflections(db, rival.id)) == 1


def test_build_context_includes_reflections(db):
    """Reflections ride both prompts as their own CHỦ QUAN section (newest
    first) — and the plan prompt carries the cross-check rule."""
    from app.features.tactics.prompt import INTERVIEW_SYSTEM_PROMPT, PLAN_SYSTEM_PROMPT

    rival = _player(db, "Lợi Phạm")
    ctx = service.build_context(db, db.get(Player, rival.id))
    assert "PHÂN TÍCH CỦA HỌC TRÒ SAU CÁC TRẬN VỚI LỢI PHẠM" in ctx
    assert "(chưa có)" in ctx

    service.add_reflection(db, schemas.ReflectionIn(player_id=rival.id, text="Cũ."))
    service.add_reflection(db, schemas.ReflectionIn(player_id=rival.id, text="Mới."))
    ctx = service.build_context(db, db.get(Player, rival.id))
    assert ctx.index("Mới.") < ctx.index("Cũ.")  # newest first
    assert "ĐỐI CHIẾU" in PLAN_SYSTEM_PROMPT  # cross-check rule
    assert "PHÂN TÍCH CỦA HỌC TRÒ" in INTERVIEW_SYSTEM_PROMPT  # no re-asking


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
    # Kèo-direction legend (2026-08-17: a live plan flipped 'được chấp' into
    # 'bị chấp') — the context spells the direction out and bans rewording.
    assert "CHÚ GIẢI KÈO" in ctx
    assert "cấm tự đổi sang 'bị chấp'" in ctx
    from app.features.tactics.prompt import PLAN_SYSTEM_PROMPT
    assert "KHÔNG viết 'bị chấp'" in PLAN_SYSTEM_PROMPT
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
