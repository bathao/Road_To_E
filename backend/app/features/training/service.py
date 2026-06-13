"""Business logic for the Training Center tab.

Programs are static (program.py); this module materialises the player's progress
through them: it opens the next session on demand, records ticks and completions,
and advances/unlocks levels. Sessions are created lazily — a tc_session row only
appears once its "Day" tile has been opened.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy.orm import Session

from app.features.training import program, schemas
from app.features.training.models import (
    TrainingSession,
    TrainingSessionItem,
    TrainingState,
)


# ---------------------------------------------------------------- state
def ensure_state(db: Session) -> TrainingState:
    """Return the singleton state row, creating it on first use.

    The cutover date (when Training Center takes over physical-training input)
    is stamped here, once, on first run — days before it keep their legacy
    tracker checklist data untouched.
    """
    state = db.get(TrainingState, 1)
    if state is None:
        today = dt.date.today()
        state = TrainingState(
            id=1,
            current_level="foundation",
            unlocked_levels="foundation",
            level_since=today,
            cutover_date=today,
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _unlocked_set(state: TrainingState) -> set[str]:
    return {s for s in (state.unlocked_levels or "").split(",") if s}


# ---------------------------------------------------------------- sessions
def _done_count(db: Session, level: str) -> int:
    return (
        db.query(TrainingSession)
        .filter(TrainingSession.level == level, TrainingSession.status == "done")
        .count()
    )


def _get_row(db: Session, level: str, day_index: int) -> TrainingSession | None:
    return (
        db.query(TrainingSession)
        .filter(
            TrainingSession.level == level,
            TrainingSession.day_index == day_index,
        )
        .first()
    )


def _materialise(db: Session, level: str, day_index: int) -> TrainingSession:
    """Get (or lazily create) the session row for (level, day_index)."""
    row = _get_row(db, level, day_index)
    if row is not None:
        return row
    planned = program.planned_session(level, day_index)
    # Progressive overload only applies on the endless maintenance level; on the
    # finite levels (day_index 1..21) cycle 0 means base targets, unchanged.
    cycle = program.cycle_of(day_index) if level == program.MAINTENANCE_LEVEL else 0
    row = TrainingSession(
        level=level,
        day_index=day_index,
        day_type=planned.day_type,
        status="unlocked",
    )
    for i, ex in enumerate(planned.exercises):
        row.items.append(
            TrainingSessionItem(
                exercise_key=ex.key,
                target_json=json.dumps(program.scaled_target(ex, cycle)),
                sort_order=i,
            )
        )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def open_session(db: Session) -> tuple[TrainingSession, bool]:
    """The current open session. Advances/unlocks levels as needed.

    Returns (session, level_complete) where level_complete is True only when the
    very last level's program is finished and there is nothing further to open.
    """
    state = ensure_state(db)
    level = state.current_level
    done = _done_count(db, level)

    if done >= program.SESSIONS_PER_LEVEL:
        nxt = program.next_level(level)
        if nxt is None:
            # Last level finished — DON'T dead-end. Keep opening the next session
            # (maintenance cycles with progressive overload, see program.py).
            return _materialise(db, level, done + 1), False
        unlocked = _unlocked_set(state) | {nxt}
        state.unlocked_levels = ",".join(l for l in program.LEVELS if l in unlocked)
        state.current_level = nxt
        state.level_since = dt.date.today()
        db.commit()
        level, done = nxt, 0

    return _materialise(db, level, done + 1), False


# ---------------------------------------------------------------- serialisation
def _item_out(item: TrainingSessionItem) -> schemas.ItemOut:
    ex = program.EXERCISES.get(item.exercise_key)
    return schemas.ItemOut(
        id=item.id,
        exercise_key=item.exercise_key,
        name_vi=ex.name_vi if ex else item.exercise_key,
        muscle=ex.muscle if ex else "",
        tt_benefit=ex.tt_benefit if ex else "",
        kind=ex.kind if ex else "reps",
        target=json.loads(item.target_json),
        per_side=ex.per_side if ex else False,
        gif=ex.gif if ex else "",
        form_cue=ex.form_cue if ex else "",
        done=item.done,
        is_prescribed=item.is_prescribed,
        rx_reason=item.rx_reason,
    )


def to_session_out(session: TrainingSession) -> schemas.SessionOut:
    items = sorted(session.items, key=lambda it: it.sort_order)
    total = len(items)
    done_count = sum(1 for it in items if it.done)
    exs = [program.EXERCISES[it.exercise_key] for it in items
           if it.exercise_key in program.EXERCISES]
    return schemas.SessionOut(
        id=session.id,
        level=session.level,
        level_vi=program.LEVEL_VI.get(session.level, session.level),
        day_index=session.day_index,
        day_type=session.day_type,
        focus_vi=program.DAY_FOCUS_VI.get(session.day_type, ""),
        est_minutes=program.estimate_minutes(exs),
        status=session.status,
        done_count=done_count,
        total=total,
        progress_pct=round(100 * done_count / total) if total else 0,
        done_on=session.done_on,
        note=session.note,
        items=[_item_out(it) for it in items],
    )


# ------------------------------------------------- adaptive prescription
# Physically-trainable weak aspects from the Video Analysis skill ledger ->
# a corrective exercise. Only aspects off-table training can actually address.
_PRESCRIPTION_MAP = {
    "stance_posture": ("side_plank", "tư thế / giữ trụ"),
    "footwork": ("lateral_toe_steps", "di chuyển chân"),
    "physical": ("plank", "thể lực / lõi"),
}


def prescription_for(db: Session) -> tuple[str, str] | None:
    """Pick a corrective exercise from the weakest relevant video-analysis skill.

    Best-effort and decoupled: reads the va_skill ledger directly (no HTTP, no
    Head Coach). Returns (exercise_key, reason) or None. Any failure → None.
    """
    try:
        from app.features.video_analysis.models import VASkill
    except Exception:
        return None
    try:
        rows = (
            db.query(VASkill)
            .filter(VASkill.aspect.in_(list(_PRESCRIPTION_MAP)))
            .all()
        )
    except Exception:
        return None

    weak = [
        s for s in rows
        if (s.rating is not None and s.rating <= 5)
        or s.status in ("weakness", "needs_work")
    ]
    if not weak:
        return None
    # Highest priority first (lower number = more urgent), then lowest rating.
    weak.sort(key=lambda s: (s.priority or 99, s.rating if s.rating is not None else 99))
    top = weak[0]
    ex_key, aspect_label = _PRESCRIPTION_MAP[top.aspect]
    reason = f"Video cho thấy {aspect_label} còn yếu"
    if top.assessment:
        snippet = top.assessment.strip().split("\n")[0][:90]
        reason = f"{reason}: {snippet}"
    return ex_key, reason


def _apply_prescription(db: Session, session: TrainingSession) -> None:
    """Inject one corrective exercise into the open session (once)."""
    if session.status == "done":
        return
    if any(it.is_prescribed for it in session.items):
        return  # already carries a prescribed exercise
    rx = prescription_for(db)
    if rx is None:
        return
    ex_key, reason = rx
    ex = program.EXERCISES.get(ex_key)
    if ex is None or any(it.exercise_key == ex_key for it in session.items):
        return  # unknown, or the base session already includes it
    max_order = max((it.sort_order for it in session.items), default=-1)
    session.items.append(
        TrainingSessionItem(
            exercise_key=ex_key,
            target_json=json.dumps(ex.target),
            is_prescribed=True,
            rx_reason=reason,
            sort_order=max_order + 1,
        )
    )
    session.adapted = True
    db.commit()
    db.refresh(session)


def get_today(db: Session) -> schemas.SessionOut:
    session, _ = open_session(db)
    _apply_prescription(db, session)
    return to_session_out(session)


def session_on_date(db: Session, day: dt.date) -> TrainingSession | None:
    """The session completed on a given calendar date (for the tracker's
    read-only Physical-row detail view)."""
    return (
        db.query(TrainingSession)
        .filter(
            TrainingSession.status == "done",
            TrainingSession.done_on == day,
        )
        .order_by(TrainingSession.id.desc())
        .first()
    )


# ---------------------------------------------------------------- mutations
def tick_item(
    db: Session, session_id: int, item_id: int, done: bool
) -> schemas.SessionOut | None:
    item = db.get(TrainingSessionItem, item_id)
    if item is None or item.session_id != session_id:
        return None
    item.done = done
    item.done_at = dt.datetime.now() if done else None
    db.commit()
    session = db.get(TrainingSession, session_id)
    return to_session_out(session) if session else None


def complete_session(
    db: Session, level: str, day_index: int, note: str | None
) -> schemas.SessionOut:
    """Mark a session done, stamping the calendar date it was completed."""
    session = _materialise(db, level, day_index)
    session.status = "done"
    session.done_on = dt.date.today()
    session.completed_at = dt.datetime.now()
    if note is not None:
        session.note = note
    exs = [program.EXERCISES[it.exercise_key] for it in session.items
           if it.exercise_key in program.EXERCISES]
    session.duration_min = program.estimate_minutes(exs)
    db.commit()
    db.refresh(session)
    return to_session_out(session)


# ---------------------------------------------------------------- grid / levels
def program_grid(db: Session, level: str | None = None) -> schemas.ProgramOut:
    state = ensure_state(db)
    level = level or state.current_level
    done = _done_count(db, level)
    n = program.SESSIONS_PER_LEVEL

    # The top level is endless: it repeats in cycles (Vòng) with progressive
    # overload. Finite levels always show cycle 0. The grid shows the CURRENT
    # cycle's 21 tiles; tile.day_index stays the ABSOLUTE session index so the
    # tick/complete API keeps addressing the right row.
    is_maint = level == program.MAINTENANCE_LEVEL
    cycle = (done // n) if (is_maint and n) else 0
    base = cycle * n
    within_done = done - base
    open_within = min(within_done + 1, n)

    tiles: list[schemas.TileOut] = []
    for i in range(1, n + 1):
        abs_index = base + i
        planned = program.planned_session(level, abs_index)
        thumb = planned.exercises[0].gif if planned.exercises else ""
        if i <= within_done:
            status = "done"
        elif i == open_within:
            status = "unlocked"
        else:
            status = "locked"
        tiles.append(
            schemas.TileOut(
                day_index=abs_index,
                day_type=planned.day_type,
                focus_vi=planned.focus_vi,
                status=status,
                thumb=thumb,
            )
        )

    return schemas.ProgramOut(
        level=level,
        level_vi=program.LEVEL_VI.get(level, level),
        goal_vi=program.LEVEL_GOAL_VI.get(level, ""),
        safety_note=program.SAFETY_NOTE_VI,
        cycle=cycle + 1,  # 1-based "Vòng N"
        total_sessions=n,
        completed=within_done,
        progress_pct=round(100 * within_done / n) if n else 0,
        tiles=tiles,
    )


# ------------------------------------------------- Daily Tracker integration
PHYSICAL_YELLOW_RATIO = 0.7  # ≥70% items done -> the day counts as "yellow"


def get_cutover(db: Session) -> dt.date | None:
    """The date Training Center took over as the physical-training input."""
    state = db.get(TrainingState, 1)
    return state.cutover_date if state else None


def done_date_bounds(db: Session) -> tuple[dt.date | None, dt.date | None]:
    """(earliest, latest) calendar date a session was completed — for the
    tracker's data-range bounds (so the grid opens on a TC-only day too)."""
    from sqlalchemy import func

    lo = db.query(func.min(TrainingSession.done_on)).scalar()
    hi = db.query(func.max(TrainingSession.done_on)).scalar()
    return lo, hi


def physical_day_map(
    db: Session, date_from: dt.date, date_to: dt.date
) -> dict[str, dict]:
    """Completed sessions keyed by the calendar date they were done.

    Used by the Daily Tracker to render the Physical row and to count physical
    days from the cutover forward. Sessions completed before the cutover are
    ignored (those days keep their legacy checklist data as the source).
    """
    cutover = get_cutover(db)
    rows = (
        db.query(TrainingSession)
        .filter(
            TrainingSession.status == "done",
            TrainingSession.done_on.isnot(None),
            TrainingSession.done_on >= date_from,
            TrainingSession.done_on <= date_to,
        )
        .all()
    )
    out: dict[str, dict] = {}
    for s in rows:
        if cutover is not None and s.done_on < cutover:
            continue
        total = len(s.items)
        done = sum(1 for it in s.items if it.done)
        iso = s.done_on.isoformat()
        out[iso] = {
            "done": done,
            "total": total,
            "pct": round(100 * done / total) if total else 0,
            "is_yellow": bool(total) and done / total >= PHYSICAL_YELLOW_RATIO,
            "focus_vi": program.DAY_FOCUS_VI.get(s.day_type, ""),
            "day_index": s.day_index,
            "level_vi": program.LEVEL_VI.get(s.level, s.level),
        }
    return out


def _weekly_summary(
    last7: int, last30: int, days_since: int | None, level_vi: str
) -> str:
    """A short, data-driven coach line (supportive, not abusive — we trust the
    user). No flattery: it reports the numbers and a concrete nudge."""
    if last30 == 0:
        return (
            "Chưa có buổi nào gần đây. Bắt đầu lại từ buổi hôm nay — "
            "đều đặn quan trọng hơn cường độ."
        )
    if days_since is not None and days_since >= 4:
        return (
            f"Đã {days_since} ngày chưa tập. Quay lại buổi hôm nay đi, "
            "giữ nhịp mới có tác dụng."
        )
    if last7 >= 5:
        return f"Tuần này {last7} buổi — nhịp tốt ở cấp {level_vi}. Giữ vậy."
    if last7 >= 3:
        return f"Tuần này {last7} buổi. Ổn, ráng thêm để chạm mốc 5 buổi/tuần."
    return f"Tuần này mới {last7} buổi. Cần đều hơn — mục tiêu 5 buổi/tuần."


def report(db: Session) -> schemas.ReportOut:
    """Tier-1 brain view for the Head Coach: training load, adherence, volume."""
    state = ensure_state(db)
    today = dt.date.today()
    done = (
        db.query(TrainingSession)
        .filter(TrainingSession.status == "done", TrainingSession.done_on.isnot(None))
        .order_by(TrainingSession.done_on.desc())
        .all()
    )

    last7 = sum(1 for s in done if (today - s.done_on).days < 7)
    last30 = sum(1 for s in done if (today - s.done_on).days < 30)
    last_date = done[0].done_on if done else None
    days_since = (today - last_date).days if last_date else None

    day_type_counts: dict[str, int] = {dt_: 0 for dt_ in program.DAY_TYPES}
    muscle: dict[str, int] = {}
    for s in done:
        day_type_counts[s.day_type] = day_type_counts.get(s.day_type, 0) + 1
        for it in s.items:
            if not it.done:
                continue
            ex = program.EXERCISES.get(it.exercise_key)
            if ex:
                muscle[ex.muscle] = muscle.get(ex.muscle, 0) + 1

    muscle_volume = sorted(
        (schemas.MuscleVolume(muscle=m, times=t) for m, t in muscle.items()),
        key=lambda mv: -mv.times,
    )
    recent = [
        schemas.RecentSession(
            done_on=s.done_on,
            level=s.level,
            day_index=s.day_index,
            focus_vi=program.DAY_FOCUS_VI.get(s.day_type, ""),
            done_count=sum(1 for it in s.items if it.done),
            total=len(s.items),
        )
        for s in done[:10]
    ]
    level_vi = program.LEVEL_VI.get(state.current_level, state.current_level)
    return schemas.ReportOut(
        current_level=state.current_level,
        current_level_vi=level_vi,
        cutover_date=state.cutover_date,
        total_sessions_done=len(done),
        sessions_last_7d=last7,
        sessions_last_30d=last30,
        last_session_date=last_date,
        days_since_last=days_since,
        day_type_counts=day_type_counts,
        muscle_volume=muscle_volume,
        levels=level_overview(db).levels,
        recent=recent,
        summary_vi=_weekly_summary(last7, last30, days_since, level_vi),
    )


def level_overview(db: Session) -> schemas.LevelOut:
    # Settle any pending level advance so current_level matches what /today shows.
    open_session(db)
    state = ensure_state(db)
    unlocked = _unlocked_set(state)
    levels = [
        schemas.LevelInfo(
            key=key,
            label_vi=program.LEVEL_VI.get(key, key),
            goal_vi=program.LEVEL_GOAL_VI.get(key, ""),
            unlocked=key in unlocked,
            # Cap at the level size for display (the endless top level can exceed
            # it across maintenance cycles; the chip just shows ≤ total).
            completed=min(_done_count(db, key), program.SESSIONS_PER_LEVEL),
            total=program.SESSIONS_PER_LEVEL,
        )
        for key in program.LEVELS
    ]
    return schemas.LevelOut(current_level=state.current_level, levels=levels)
