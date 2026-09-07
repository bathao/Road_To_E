"""Tracking board (Journal tab, 2026-08-24): task CRUD, the daily-check
streak math, and the coach bundle's NHIỆM VỤ section."""
from __future__ import annotations

import datetime as dt

from app.features.tracker import service
from app.features.tracker.models import Task, TaskCheck

TODAY = dt.date.today()


def _post(client, title, **kw):
    return client.post(
        "/api/tracker/tasks", json={"title": title, **kw}
    )


def test_task_crud_returns_fresh_list(client, db):
    out = _post(client, "Tập giao bóng đục", source="coach", is_daily=True).json()
    assert [t["title"] for t in out["tasks"]] == ["Tập giao bóng đục"]
    t1 = out["tasks"][0]
    assert (t1["source"], t1["status"], t1["is_daily"]) == ("coach", "todo", True)
    assert t1["streak"] == 0 and t1["checked_today"] is False

    out = _post(client, "Quay video trận đấu").json()  # defaults: self, one-off
    assert len(out["tasks"]) == 2
    t2 = out["tasks"][1]
    assert (t2["source"], t2["is_daily"]) == ("self", False)

    # Status walk: todo -> doing -> done (done_at set) -> back to todo (cleared).
    out = client.patch(f"/api/tracker/tasks/{t2['id']}", json={"status": "doing"}).json()
    assert out["tasks"][1]["status"] == "doing"
    out = client.patch(f"/api/tracker/tasks/{t2['id']}", json={"status": "done"}).json()
    assert out["tasks"][1]["status"] == "done"
    assert out["tasks"][1]["done_at"] is not None
    out = client.patch(f"/api/tracker/tasks/{t2['id']}", json={"status": "todo"}).json()
    assert out["tasks"][1]["done_at"] is None

    # Edit fields; unknown id -> 404; delete removes the row + returns the list.
    out = client.patch(
        f"/api/tracker/tasks/{t2['id']}", json={"title": "Quay video", "source": "ai"}
    ).json()
    assert (out["tasks"][1]["title"], out["tasks"][1]["source"]) == ("Quay video", "ai")
    assert client.patch("/api/tracker/tasks/999", json={"status": "done"}).status_code == 404
    out = client.delete(f"/api/tracker/tasks/{t2['id']}").json()
    assert [t["title"] for t in out["tasks"]] == ["Tập giao bóng đục"]
    assert db.query(Task).count() == 1


def test_daily_check_and_streak(client, db):
    tid = _post(client, "Flick trái", source="coach", is_daily=True).json()["tasks"][0]["id"]

    # Tick 3 consecutive days ending today -> streak 3, checked_today True.
    for back in (2, 1, 0):
        out = client.post(
            f"/api/tracker/tasks/{tid}/check",
            json={"date": (TODAY - dt.timedelta(days=back)).isoformat(), "checked": True},
        ).json()
    t = out["tasks"][0]
    assert (t["checked_today"], t["streak"]) == (True, 3)
    assert t["last_check"] == TODAY.isoformat()

    # Un-tick today (mis-click): streak falls back to the run ending yesterday.
    out = client.post(
        f"/api/tracker/tasks/{tid}/check",
        json={"date": TODAY.isoformat(), "checked": False},
    ).json()
    t = out["tasks"][0]
    assert (t["checked_today"], t["streak"]) == (False, 2)

    # A gap breaks the streak: lone tick 5 days ago contributes nothing.
    db.query(TaskCheck).delete()
    db.add(TaskCheck(task_id=tid, date=TODAY - dt.timedelta(days=5)))
    db.commit()
    assert service.list_tasks(db).tasks[0].streak == 0

    # Ticking twice is idempotent (no unique-constraint blowup).
    for _ in range(2):
        client.post(
            f"/api/tracker/tasks/{tid}/check",
            json={"date": TODAY.isoformat(), "checked": True},
        )
    assert db.query(TaskCheck).filter(TaskCheck.date == TODAY).count() == 1


def test_done_tasks_drop_off_after_a_week(client, db):
    tid = _post(client, "Old chore").json()["tasks"][0]["id"]
    client.patch(f"/api/tracker/tasks/{tid}", json={"status": "done"})
    # Fresh done -> still listed; 8-day-old done -> gone (row survives).
    assert len(service.list_tasks(db).tasks) == 1
    t = db.get(Task, tid)
    t.done_at = t.done_at - dt.timedelta(days=8)
    db.commit()
    assert service.list_tasks(db).tasks == []
    assert db.query(Task).count() == 1


def test_coach_bundle_reads_tasks(client, db):
    _post(client, "Tập giao bóng đục", source="coach", is_daily=True)
    tid = _post(client, "Xong rồi").json()["tasks"][1]["id"]
    client.patch(f"/api/tracker/tasks/{tid}", json={"status": "done"})

    from app.features.head_coach import service as hc_service

    bundle = hc_service.gather_bundle(db)
    # Open tasks only — done ones never reach the prompt.
    assert [x["title"] for x in bundle.tasks] == ["Tập giao bóng đục"]
    assert bundle.tasks[0]["daily"] is True
    text = hc_service._bundle_to_text(bundle)
    assert "=== NHIỆM VỤ ĐANG THEO" in text
    assert "Tập giao bóng đục" in text
    assert "chuỗi 0 ngày" in text
