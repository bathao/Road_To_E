"""Remember board (Journal tab, 2026-09-24): standing reminders the player
re-reads daily — CRUD, priority order, and the coach bundle sections."""
from __future__ import annotations

from app.features.tracker import service
from app.features.tracker.models import Memo


def _post(client, text):
    return client.post("/api/tracker/memos", json={"text": text})


def test_memo_crud_returns_fresh_ordered_list(client, db):
    out = _post(client, "**Đỡ giao bóng**: đọc xoáy trước, quyết định mặt vợt").json()
    assert [m["text"] for m in out["memos"]] == [
        "**Đỡ giao bóng**: đọc xoáy trước, quyết định mặt vợt"
    ]
    out = _post(client, "Luôn quan sát tay, vợt đối thủ").json()
    assert len(out["memos"]) == 2
    # New memos append at the bottom (priority order = list order).
    assert [m["sort_order"] for m in out["memos"]] == [1, 2]

    m2 = out["memos"][1]
    out = client.patch(
        f"/api/tracker/memos/{m2['id']}", json={"text": "Quan sát tay + vợt đối thủ"}
    ).json()
    assert out["memos"][1]["text"] == "Quan sát tay + vợt đối thủ"
    assert client.patch("/api/tracker/memos/999", json={"text": "x"}).status_code == 404
    # Blank / whitespace-only text is rejected — a memo is never saved empty.
    assert client.post("/api/tracker/memos", json={"text": "   "}).status_code == 422
    assert client.post("/api/tracker/memos", json={"text": ""}).status_code == 422
    assert client.patch(f"/api/tracker/memos/{m2['id']}", json={"text": " "}).status_code == 422
    assert db.query(Memo).count() == 2

    out = client.delete(f"/api/tracker/memos/{m2['id']}").json()
    assert len(out["memos"]) == 1
    assert client.delete("/api/tracker/memos/999").status_code == 404
    assert db.query(Memo).count() == 1


def test_memo_reorder_sets_priority(client, db):
    ids = []
    for t in ("A", "B", "C"):
        ids = [m["id"] for m in _post(client, t).json()["memos"]]
    a, b, c = ids

    out = client.put("/api/tracker/memos/order", json={"ids": [c, a, b]}).json()
    assert [m["text"] for m in out["memos"]] == ["C", "A", "B"]
    assert [m["sort_order"] for m in out["memos"]] == [1, 2, 3]
    # GET agrees with the mutation's list.
    assert [m["text"] for m in client.get("/api/tracker/memos").json()["memos"]] == ["C", "A", "B"]

    # A stale / partial list is refused, order unchanged.
    assert client.put("/api/tracker/memos/order", json={"ids": [a, b]}).status_code == 409
    assert client.put("/api/tracker/memos/order", json={"ids": [a, b, c, 999]}).status_code == 409
    assert client.put("/api/tracker/memos/order", json={"ids": [a, a, b]}).status_code == 409
    assert [m.text for m in service.list_memos(db).memos] == ["C", "A", "B"]

    # A memo created after a reorder still lands at the bottom.
    out = _post(client, "D").json()
    assert [m["text"] for m in out["memos"]] == ["C", "A", "B", "D"]


def test_coach_bundles_read_memos(client, db):
    _post(client, "Xoay chân phải vào khi giật")
    _post(client, "Giao dài trước, ngắn sau")

    from app.features.head_coach import service as hc_service

    bundle = hc_service.gather_bundle(db)
    assert [x["text"] for x in bundle.memos] == [
        "Xoay chân phải vào khi giật",
        "Giao dài trước, ngắn sau",
    ]
    text = hc_service._bundle_to_text(bundle)
    assert "=== ĐIỀU HỌC TRÒ TỰ NHẮC MÌNH MỖI NGÀY" in text
    assert text.index("Xoay chân phải") < text.index("Giao dài trước")



def test_recap_bundle_reads_memos(client, db, monkeypatch):
    """The weekly recap's sources carry the board too (as it stands at
    generation time — a memo has no history)."""
    import datetime as dt
    import json

    from app.features.head_coach import service as hc_service
    from app.features.head_coach.models import HeadCoachRecap
    from app.features.tracker.models import Activity

    from conftest import category_id

    # A recap needs SOME logged data in its window.
    db.add(Activity(
        date=dt.date.today(),
        category_id=category_id(db, "train_with_coach"),
        duration_minutes=60,
    ))
    db.commit()
    _post(client, "Xoay chân phải vào khi giật")
    _post(client, "Giao dài trước, ngắn sau")
    monkeypatch.setattr(
        hc_service,
        "_call_recap_model",
        lambda *a, **k: {
            "headline": "ok", "overall": "ok",
            "went_well": [], "concerns": [], "focus_next": [],
        },
    )
    monkeypatch.setattr(hc_service, "resolve_model", lambda: "test-model")

    out = hc_service.start_recap(db, "week", today=dt.date.today())
    hc_service.run_recap_job(out.id, db)
    row = db.query(HeadCoachRecap).first()
    assert row.status == "done"
    bundle = json.loads(row.sources_json)
    assert [x["text"] for x in bundle["memos"]] == [
        "Xoay chân phải vào khi giật",
        "Giao dài trước, ngắn sau",
    ]
    rtext = hc_service._recap_bundle_to_text(bundle)
    assert "bảng Remember" in rtext and "Giao dài trước" in rtext


def test_empty_board_renders_placeholder(client, db):
    from app.features.head_coach import service as hc_service

    text = hc_service._bundle_to_text(hc_service.gather_bundle(db))
    assert "(bảng ghi nhớ trống)" in text
