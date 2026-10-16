"""The Tracking (tasks) and Remember (memos) boards.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.base import utcnow as _utcnow
from app.core.errors import Conflict, NotFound
from app.features.tracker import schemas
from app.features.tracker.models import (
    Memo,
    Task,
    TaskCheck,
)

# Done tasks linger on the board this long, then drop off the list (the row
# itself is never deleted — restore stays possible via direct status PATCH
# while it's still listed).
_TASK_DONE_KEEP_DAYS = 7


def _task_streak(check_dates: set[dt.date], today: dt.date) -> int:
    """Consecutive practiced days ending today — or ending yesterday when
    today isn't ticked yet (the streak isn't broken until the day is over)."""
    day = today if today in check_dates else today - dt.timedelta(days=1)
    streak = 0
    while day in check_dates:
        streak += 1
        day -= dt.timedelta(days=1)
    return streak


def _task_to_out(t: Task, today: dt.date) -> schemas.TaskOut:
    checks = {c.date for c in t.checks}
    return schemas.TaskOut(
        id=t.id,
        title=t.title,
        note=t.note or "",
        source=t.source,
        status=t.status,
        is_daily=t.is_daily,
        created_at=t.created_at,
        done_at=t.done_at,
        checked_today=today in checks,
        streak=_task_streak(checks, today) if t.is_daily else 0,
        last_check=max(checks) if checks else None,
    )


def list_tasks(db: Session, today: dt.date | None = None) -> schemas.TasksOut:
    """The board: every open task + tasks done in the last week, oldest
    first within status (stable — new tasks append at the bottom)."""
    today = today or dt.date.today()
    cutoff = dt.datetime.combine(
        today - dt.timedelta(days=_TASK_DONE_KEEP_DAYS), dt.time.min
    )
    rows = (
        db.query(Task)
        .filter((Task.status != "done") | (Task.done_at >= cutoff))
        .order_by(Task.sort_order, Task.id)
        .options(selectinload(Task.checks))
        .all()
    )
    return schemas.TasksOut(tasks=[_task_to_out(t, today) for t in rows])


def create_task(db: Session, payload: schemas.TaskIn) -> schemas.TasksOut:
    db.add(Task(
        title=payload.title.strip(),
        note=payload.note.strip(),
        source=payload.source,
        is_daily=payload.is_daily,
    ))
    db.commit()
    return list_tasks(db)


def update_task(db: Session, task_id: int, payload: schemas.TaskUpdate) -> schemas.TasksOut:
    t = db.get(Task, task_id)
    if t is None:
        raise NotFound(f"task {task_id} not found")
    if payload.title is not None:
        t.title = payload.title.strip()
    if payload.note is not None:
        t.note = payload.note.strip()
    if payload.source is not None:
        t.source = payload.source
    if payload.is_daily is not None:
        t.is_daily = payload.is_daily
    if payload.status is not None and payload.status != t.status:
        t.status = payload.status
        t.done_at = _utcnow() if payload.status == "done" else None
    db.commit()
    return list_tasks(db)


def delete_task(db: Session, task_id: int) -> schemas.TasksOut:
    t = db.get(Task, task_id)
    if t is None:
        raise NotFound(f"task {task_id} not found")
    db.delete(t)  # checks go with it (delete-orphan)
    db.commit()
    return list_tasks(db)


def set_task_check(
    db: Session, task_id: int, payload: schemas.TaskCheckIn
) -> schemas.TasksOut:
    """Tick/un-tick one day of a daily task (idempotent both ways)."""
    t = db.get(Task, task_id)
    if t is None:
        raise NotFound(f"task {task_id} not found")
    existing = (
        db.query(TaskCheck)
        .filter(TaskCheck.task_id == task_id, TaskCheck.date == payload.date)
        .first()
    )
    if payload.checked and existing is None:
        db.add(TaskCheck(task_id=task_id, date=payload.date))
    elif not payload.checked and existing is not None:
        db.delete(existing)
    db.commit()
    return list_tasks(db)


def _memo_to_out(m: Memo) -> schemas.MemoOut:
    return schemas.MemoOut(
        id=m.id,
        text=m.text,
        sort_order=m.sort_order,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def list_memos(db: Session) -> schemas.MemosOut:
    """The Remember board in priority order (sort_order, then id — a new
    memo lands at the bottom until the user moves it)."""
    rows = db.query(Memo).order_by(Memo.sort_order, Memo.id).all()
    return schemas.MemosOut(memos=[_memo_to_out(m) for m in rows])


def create_memo(db: Session, payload: schemas.MemoIn) -> schemas.MemosOut:
    last = db.query(func.max(Memo.sort_order)).scalar()
    db.add(Memo(text=payload.text.strip(), sort_order=(last or 0) + 1))
    db.commit()
    return list_memos(db)


def update_memo(db: Session, memo_id: int, payload: schemas.MemoUpdate) -> schemas.MemosOut:
    m = db.get(Memo, memo_id)
    if m is None:
        raise NotFound(f"memo {memo_id} not found")
    m.text = payload.text.strip()
    db.commit()
    return list_memos(db)


def delete_memo(db: Session, memo_id: int) -> schemas.MemosOut:
    m = db.get(Memo, memo_id)
    if m is None:
        raise NotFound(f"memo {memo_id} not found")
    db.delete(m)
    db.commit()
    return list_memos(db)


def reorder_memos(db: Session, payload: schemas.MemoReorderIn) -> schemas.MemosOut:
    """Set the priority order from the full id list. Rejects a list that is
    not exactly the current set of memos (a stale GUI must not silently
    drop or duplicate a card)."""
    rows = db.query(Memo).all()
    current = {m.id for m in rows}
    if sorted(payload.ids) != sorted(current) or len(payload.ids) != len(current):
        raise Conflict("ids must list every current memo exactly once")
    by_id = {m.id: m for m in rows}
    for i, mid in enumerate(payload.ids, start=1):
        by_id[mid].sort_order = i
    db.commit()
    return list_memos(db)
