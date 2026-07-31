"""Coach & Recap row (session notes): gating, cell rendering, lifecycle, bundle."""
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


def test_cell_render_snippet_counts_and_export(client, db):
    _add_coach_session(client, db)
    _post_note(
        client,
        DAY,
        "advice",
        "Stay lower on FH loop drills",
        ["fh_topspin", "footwork"],
    )

    iso = DAY.isoformat()
    week = client.get(f"/api/tracker/weeks?start={iso}").json()
    cat = next(c for c in week["categories"] if c["key"] == "coach_recap")
    assert cat["type"] == "session_note"

    # Single item -> kind icon + snippet.
    cell = week["cells"][f"{cat['id']}|{iso}"]["display"]
    assert cell.startswith("🧑‍🏫 ")
    assert "…" in cell  # text longer than the snippet cap

    # Full items + coach-day gate data travel alongside the cells.
    assert [n["text"] for n in week["session_notes"][iso]] == [
        "Stay lower on FH loop drills"
    ]
    assert iso in week["coach_days"]

    # Second item -> the cell collapses to per-kind counts.
    _post_note(client, DAY, "recap", "Serve practice 30 min", ["serve"])
    week = client.get(f"/api/tracker/weeks?start={iso}").json()
    assert week["cells"][f"{cat['id']}|{iso}"]["display"] == "🧑‍🏫 1 · 📋 1"

    # Export renders every item in full with prefixes + tag labels.
    csv_text = client.get(
        f"/api/tracker/export?from={iso}&to={iso}&format=csv"
    ).text
    assert "Coach: Stay lower on FH loop drills [FH Topspin, Footwork]" in csv_text
    assert "Recap: Serve practice 30 min [Serve]" in csv_text


def test_drills_numbered_in_entry_order(client, db):
    _add_coach_session(client, db)
    _post_note(client, DAY, "drill", "FH topspin vs block", ["fh_topspin"])
    _post_note(client, DAY, "drill", "BH push short balls", ["bh_push"])
    _post_note(client, DAY, "advice", "Stay lower")

    iso = DAY.isoformat()
    week = client.get(f"/api/tracker/weeks?start={iso}").json()
    cat = next(c for c in week["categories"] if c["key"] == "coach_recap")
    # Counts render in canonical kind order: advice · drills · recaps.
    assert week["cells"][f"{cat['id']}|{iso}"]["display"] == "🧑‍🏫 1 · 🏓 2"

    # Export numbers drills by entry order (nothing stored).
    csv_text = client.get(
        f"/api/tracker/export?from={iso}&to={iso}&format=csv"
    ).text
    assert "Drill 1: FH topspin vs block [FH Topspin]" in csv_text
    assert "Drill 2: BH push short balls [BH Push]" in csv_text

    # Drills never enter the advice checklist, and is_done is ignored.
    active = client.get("/api/tracker/session-notes/active").json()
    assert [n["text"] for n in active] == ["Stay lower"]


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
