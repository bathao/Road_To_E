"""Journal (session notes): gating, lesson kind, timeline, lifecycle, bundle.
(Formerly the Coach & Recap grid row — moved to the Journal tab 2026-08-20.)"""
from __future__ import annotations

import datetime as dt

from app.features.tracker import service
from app.features.tracker.models import Activity, SessionNote

from conftest import category_id

DAY = dt.date(2026, 7, 20)


def _add_coach_session(client, db, day: dt.date = DAY, minutes: int = 120):
    resp = client.put(
        "/api/tracker/activities",
        json={
            "date": day.isoformat(),
            "category_id": category_id(db, "train_with_coach"),
            "duration_minutes": minutes,
        },
    )
    assert resp.status_code == 200


def _post_note(client, day: dt.date, kind: str, text: str, tags=None):
    return client.post(
        "/api/tracker/session-notes",
        json={
            "date": day.isoformat(),
            "kind": kind,
            "text": text,
            "tags": tags or [],
        },
    )


def test_create_requires_coach_session(client, db):
    # No coach session that day -> 400.
    resp = _post_note(client, DAY, "advice", "Toss the serve higher")
    assert resp.status_code == 400
    assert "Train with Coach" in resp.json()["detail"]

    # A 0-minute activity does not unlock the row either.
    _add_coach_session(client, db, minutes=0)
    assert _post_note(client, DAY, "advice", "Toss the serve higher").status_code == 400

    _add_coach_session(client, db, minutes=90)
    resp = _post_note(client, DAY, "advice", "Toss the serve higher", ["serve"])
    assert resp.status_code == 200
    out = resp.json()
    assert out["kind"] == "advice"
    assert out["tags"] == ["serve"]
    assert out["is_done"] is False


def test_tags_cleaned_and_canonically_ordered(client, db):
    _add_coach_session(client, db)
    resp = _post_note(
        client,
        DAY,
        "recap",
        "Multi-ball FH/BH",
        ["bh_topspin", "nonsense", "fh_topspin", "fh_topspin"],
    )
    assert resp.status_code == 200
    # Unknown dropped, dupes collapsed, canonical SESSION_NOTE_TAGS order.
    assert resp.json()["tags"] == ["fh_topspin", "bh_topspin"]


def test_grid_no_longer_carries_the_session_note_row(client, db):
    """Since 2026-08-20 the Coach & Recap row lives in the Journal tab: the
    week grid and the export skip session_note categories entirely (the old
    category row survives in existing DBs but is filtered by type)."""
    _add_coach_session(client, db)
    _post_note(client, DAY, "advice", "Stay lower on FH loop drills", ["fh_topspin"])

    iso = DAY.isoformat()
    week = client.get(f"/api/tracker/weeks?start={iso}").json()
    assert all(c["type"] != "session_note" for c in week["categories"])
    assert "session_notes" not in week and "coach_days" not in week

    csv_text = client.get(f"/api/tracker/export?from={iso}&to={iso}&format=csv").text
    assert "Stay lower on FH loop drills" not in csv_text

    # Drills never enter the advice checklist regardless of surface.
    _post_note(client, DAY, "drill", "FH topspin vs block", ["fh_topspin"])
    active = client.get("/api/tracker/session-notes/active").json()
    assert [n["text"] for n in active] == ["Stay lower on FH loop drills"]


def test_lesson_kind_needs_no_coach_session(client, db):
    """A lesson is the player's own takeaway — welcome on ANY day, no done
    lifecycle; coach kinds stay gated."""
    resp = _post_note(client, DAY, "lesson", "Giao ngắn hiệu quả hơn giao dài")
    assert resp.status_code == 200
    out = resp.json()
    assert out["kind"] == "lesson" and out["is_done"] is False
    # Coach kinds on the same (coach-less) day are still 400.
    assert _post_note(client, DAY, "advice", "x").status_code == 400
    # is_done is ignored for lessons (advice-only lifecycle).
    patched = client.patch(
        f"/api/tracker/session-notes/{out['id']}", json={"is_done": True}
    ).json()
    assert patched["is_done"] is False
    # Lessons never pollute the advice checklist.
    assert client.get("/api/tracker/session-notes/active").json() == []


def test_journal_timeline_days_and_pagination(client, db):
    """journal/days: only days WITH entries, newest first, coach names
    resolved, paginated via `before`; journal/day serves the composer flag."""
    day2 = DAY + dt.timedelta(days=2)
    day4 = DAY + dt.timedelta(days=4)
    _add_coach_session(client, db)  # DAY has a coach session
    _post_note(client, DAY, "advice", "Fix the toss", ["serve"])
    _post_note(client, day2, "lesson", "Bài học ngày 2")
    _post_note(client, day4, "lesson", "Bài học ngày 4")

    out = client.get("/api/tracker/journal/days").json()
    assert [d["date"] for d in out["days"]] == [
        day4.isoformat(), day2.isoformat(), DAY.isoformat()
    ]
    assert out["has_more"] is False
    first = out["days"][2]
    assert first["has_coach_session"] is True
    assert first["coaches"] == ["Minh Thới"]  # NULL coach_id = package coach
    assert [n["kind"] for n in first["items"]] == ["advice"]
    assert out["days"][0]["has_coach_session"] is False
    assert out["days"][0]["coaches"] == []

    # Pagination: limit 1 → newest only, has_more; `before` walks backwards.
    page = client.get("/api/tracker/journal/days?limit=1").json()
    assert [d["date"] for d in page["days"]] == [day4.isoformat()]
    assert page["has_more"] is True
    page2 = client.get(
        f"/api/tracker/journal/days?limit=1&before={day4.isoformat()}"
    ).json()
    assert [d["date"] for d in page2["days"]] == [day2.isoformat()]

    # Composer day endpoint: empty day, flag only.
    day9 = (DAY + dt.timedelta(days=9)).isoformat()
    d = client.get(f"/api/tracker/journal/day/{day9}").json()
    assert d == {
        "date": day9, "coaches": [], "has_coach_session": False, "items": [],
        "matches": [],
    }


def test_journal_match_notes(client, db):
    """The Matches area: the composer day groups the day's matches by
    opponent (one journal note per opponent per day — user 2026-08-21), a
    PATCH writes tracker_match.note (blank clears), noted opponents make
    their day a journal day, and the Tactics h2h context reads the note."""
    from app.features.tracker.models import Player, Match

    rival = Player(name="Lợi Phạm", level="equal", points=900)
    db.add(rival)
    db.commit()
    db.add(Match(
        date=DAY, category_id=category_id(db, "practice_match"),
        discipline="singles", best_of=5, my_sets=3, opp_sets=2,
        is_nonplaying=False, order_index=0, opponent_id=rival.id,
        handicap=-2,
    ))
    db.commit()
    mid = db.query(Match).first().id

    # Composer day: the match shows with an English label and empty note.
    d = client.get(f"/api/tracker/journal/day/{DAY.isoformat()}").json()
    assert [m["label"] for m in d["matches"]] == ["vs Lợi Phạm — W 3-2 (receive 2)"]
    assert d["matches"][0]["note"] == ""
    # No note and no session notes yet → not a journal day.
    assert client.get("/api/tracker/journal/days").json()["days"] == []

    # PATCH the note → the day enters the timeline carrying the noted match.
    out = client.patch(
        f"/api/tracker/matches/{mid}/note", json={"note": "  Giao ngắn ăn điểm  "}
    ).json()
    assert out["note"] == "Giao ngắn ăn điểm"
    days = client.get("/api/tracker/journal/days").json()["days"]
    assert [dd["date"] for dd in days] == [DAY.isoformat()]
    assert [m["note"] for m in days[0]["matches"]] == ["Giao ngắn ăn điểm"]

    # The Tactics h2h context quotes the note verbatim.
    from app.features.tactics import service as tactics_service
    ctx = tactics_service.build_context(db, db.get(Player, rival.id))
    assert "ghi chú của học trò: Giao ngắn ăn điểm" in ctx

    # Blank clears; the day drops off the timeline again; unknown id → 404.
    client.patch(f"/api/tracker/matches/{mid}/note", json={"note": "  "})
    assert db.get(Match, mid).note is None
    assert client.get("/api/tracker/journal/days").json()["days"] == []
    assert client.patch(
        "/api/tracker/matches/9999/note", json={"note": "x"}
    ).status_code == 404


def test_journal_matches_group_by_opponent(client, db):
    """Same opponent twice in one day → ONE journal entry: combined label,
    one note box, one timeline row. A different opponent stays separate."""
    from app.features.tracker.models import Player, Match

    tuan = Player(name="Anh Tuấn", level="equal", points=900)
    khac = Player(name="Đối Khác", level="equal", points=900)
    db.add_all([tuan, khac])
    db.commit()
    cat = category_id(db, "practice_match")
    m1 = Match(date=DAY, category_id=cat, discipline="singles", best_of=5,
               my_sets=3, opp_sets=2, is_nonplaying=False, order_index=0,
               opponent_id=tuan.id)
    m2 = Match(date=DAY, category_id=cat, discipline="singles", best_of=5,
               my_sets=3, opp_sets=1, is_nonplaying=False, order_index=1,
               opponent_id=tuan.id, handicap=-2)
    m3 = Match(date=DAY, category_id=cat, discipline="singles", best_of=5,
               my_sets=0, opp_sets=3, is_nonplaying=False, order_index=2,
               opponent_id=khac.id)
    db.add_all([m1, m2, m3])
    db.commit()

    d = client.get(f"/api/tracker/journal/day/{DAY.isoformat()}").json()
    assert [m["label"] for m in d["matches"]] == [
        "vs Anh Tuấn — W 3-2, W 3-1 (receive 2)",
        "vs Đối Khác — L 0-3",
    ]
    # The group's id targets its first match; PATCHing it notes the group.
    gid = d["matches"][0]["id"]
    assert gid == m1.id
    out = client.patch(
        f"/api/tracker/matches/{gid}/note", json={"note": "Gai công khó chịu"}
    ).json()
    assert out["label"] == "vs Anh Tuấn — W 3-2, W 3-1 (receive 2)"
    assert out["note"] == "Gai công khó chịu"

    # Timeline day carries only the noted group — combined label intact —
    # and the composer's id keeps pointing at the note-holder afterwards.
    days = client.get("/api/tracker/journal/days").json()["days"]
    assert [m["label"] for m in days[0]["matches"]] == [
        "vs Anh Tuấn — W 3-2, W 3-1 (receive 2)"
    ]
    d = client.get(f"/api/tracker/journal/day/{DAY.isoformat()}").json()
    assert d["matches"][0]["id"] == m1.id
    assert d["matches"][0]["note"] == "Gai công khó chịu"


def test_advice_lifecycle_active_list_and_done(client, db):
    _add_coach_session(client, db)
    day2 = DAY + dt.timedelta(days=2)
    _add_coach_session(client, db, day=day2)

    a1 = _post_note(client, DAY, "advice", "Fix the toss", ["serve"]).json()
    a2 = _post_note(client, day2, "advice", "Shorter backswing", ["bh_topspin"]).json()
    _post_note(client, day2, "recap", "Footwork ladder")  # recaps never appear

    active = client.get("/api/tracker/session-notes/active").json()
    assert [n["id"] for n in active] == [a1["id"], a2["id"]]  # oldest first

    # Ticking done removes it from the active list; unticking brings it back.
    resp = client.patch(
        f"/api/tracker/session-notes/{a1['id']}", json={"is_done": True}
    )
    assert resp.status_code == 200 and resp.json()["is_done"] is True
    active = client.get("/api/tracker/session-notes/active").json()
    assert [n["id"] for n in active] == [a2["id"]]

    # is_done is meaningless for recaps — silently ignored.
    recap = _post_note(client, day2, "recap", "Multiball").json()
    resp = client.patch(
        f"/api/tracker/session-notes/{recap['id']}", json={"is_done": True}
    )
    assert resp.json()["is_done"] is False


def test_update_delete_and_edge_cases(client, db):
    _add_coach_session(client, db)
    n = _post_note(client, DAY, "advice", "Old text", ["serve"]).json()

    resp = client.patch(
        f"/api/tracker/session-notes/{n['id']}",
        json={"text": "  New text  ", "tags": ["tactics"]},
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "New text"
    assert resp.json()["tags"] == ["tactics"]

    # Empty text on update is rejected (delete is the way to remove).
    assert (
        client.patch(f"/api/tracker/session-notes/{n['id']}", json={"text": "  "})
        .status_code
        == 400
    )
    assert client.patch("/api/tracker/session-notes/9999", json={}).status_code == 404

    # Items survive the coach activity being edited away (never-delete-data):
    # they stay manageable even though the day no longer unlocks NEW items.
    db.query(Activity).delete()
    db.commit()
    assert client.patch(
        f"/api/tracker/session-notes/{n['id']}", json={"is_done": True}
    ).status_code == 200
    assert _post_note(client, DAY, "advice", "blocked again").status_code == 400

    assert client.delete(f"/api/tracker/session-notes/{n['id']}").status_code == 204
    assert db.query(SessionNote).count() == 0
    # Idempotent delete, matching the other tracker deletes.
    assert client.delete(f"/api/tracker/session-notes/{n['id']}").status_code == 204


def test_tag_endpoint_matches_service_list(client):
    tags = client.get("/api/tracker/session-note-tags").json()
    assert [(t["key"], t["label"]) for t in tags] == service.SESSION_NOTE_TAGS


def test_coach_bundle_reads_advice_and_recaps(client, db):
    from app.features.head_coach import service as coach_service

    _add_coach_session(client, db)
    _post_note(client, DAY, "advice", "Fix the toss", ["serve"])
    done = _post_note(client, DAY, "advice", "Done thing").json()
    client.patch(f"/api/tracker/session-notes/{done['id']}", json={"is_done": True})
    _post_note(client, DAY, "recap", "Multi-ball FH", ["fh_topspin"])
    _post_note(client, DAY, "drill", "Serve + 3rd ball")

    bundle = coach_service.gather_bundle(db)
    assert [a["text"] for a in bundle.coach_advice] == ["Fix the toss"]
    assert bundle.coach_advice[0]["tags"] == ["Serve"]
    # Drills ride along with recaps (newest first), prefixed for the model.
    assert [r["text"] for r in bundle.session_recaps] == [
        "Bài tập: Serve + 3rd ball",
        "Multi-ball FH",
    ]

    text = coach_service._bundle_to_text(bundle)
    assert "HLV TRỰC TIẾP ĐANG DẶN" in text
    assert "Fix the toss" in text
    assert "Done thing" not in text  # completed advice stays out of the prompt


def test_coach_bundle_reads_lessons(client, db):
    """Journal lessons get their own bundle section (subjective, newest
    first) and never leak into the coach-session recap material."""
    from app.features.head_coach import service as coach_service

    _post_note(client, DAY, "lesson", "Giao ngắn ăn điểm tốt")
    _post_note(client, DAY + dt.timedelta(days=1), "lesson", "Đừng vội ở 9-9")

    bundle = coach_service.gather_bundle(db)
    assert [n["text"] for n in bundle.lessons] == [
        "Đừng vội ở 9-9", "Giao ngắn ăn điểm tốt"  # newest first
    ]
    assert bundle.session_recaps == []  # lessons are not recap material

    text = coach_service._bundle_to_text(bundle)
    assert "KINH NGHIỆM HỌC TRÒ TỰ RÚT RA" in text
    assert "Giao ngắn ăn điểm tốt" in text
