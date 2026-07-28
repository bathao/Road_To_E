"""Business logic for the Training Center tab.

Programs are static (program.py); this module materialises the player's progress
through them: it opens the next session on demand, records ticks and completions,
and advances/unlocks levels. Sessions are created lazily — a tc_session row only
appears once its "Day" tile has been opened.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

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


def get_session_row(db: Session, level: str, day_index: int) -> TrainingSession | None:
    """The materialised session row for (level, day_index), or None."""
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
    row = get_session_row(db, level, day_index)
    if row is not None:
        return row
    planned = program.planned_session(level, day_index)
    # Progressive overload only applies on the endless maintenance level; on the
    # finite levels (day_index 1..21) cycle 0 means base targets. `intensity_bias`
    # is the autoregulation adjustment from recent pain/RPE feedback.
    cycle = program.cycle_of(day_index) if level == program.MAINTENANCE_LEVEL else 0
    state = ensure_state(db)
    bias = state.intensity_bias or 0
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
                target_json=json.dumps(program.scaled_target(ex, cycle, bias)),
                sort_order=i,
            )
        )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Lost a create race on the (level, day_index) UNIQUE constraint — the
        # Head Coach's background jobs read training data on their own session
        # while the user browses the tab. The winner's row is the right one.
        db.rollback()
        row = get_session_row(db, level, day_index)
        if row is None:  # pragma: no cover — constraint hit but row missing
            raise
        return row
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
def _simple_ex(ex) -> schemas.SimpleExercise:
    return schemas.SimpleExercise(
        exercise_key=ex.key,
        name_vi=ex.name_vi,
        muscle=ex.muscle,
        tt_benefit=ex.tt_benefit,
        kind=ex.kind,
        target=dict(ex.target),
        per_side=ex.per_side,
        gif=ex.gif,
        form_cue=ex.form_cue,
        how_to=program.how_to_for(ex.key),
    )


def _item_out(item: TrainingSessionItem, exclude: set[str]) -> schemas.ItemOut:
    ex = program.EXERCISES.get(item.exercise_key)
    alts = program.alternatives_for(item.exercise_key, exclude)
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
        how_to=program.how_to_for(item.exercise_key),
        done=item.done,
        is_prescribed=item.is_prescribed,
        rx_reason=item.rx_reason,
        skipped=bool(item.skipped),
        alternatives=[schemas.ItemAlt(key=a.key, name_vi=a.name_vi) for a in alts],
    )


def to_session_out(session: TrainingSession) -> schemas.SessionOut:
    items = sorted(session.items, key=lambda it: it.sort_order)
    total = len(items)
    done_count = sum(1 for it in items if it.done)
    exs = [program.EXERCISES[it.exercise_key] for it in items
           if it.exercise_key in program.EXERCISES]
    in_session = {it.exercise_key for it in items}
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
        pain=session.pain,
        rpe=session.rpe,
        items=[_item_out(it, in_session) for it in items],
        warmup=[_simple_ex(e) for e in program.warmup_exercises()],
        cooldown=[_simple_ex(e) for e in program.cooldown_exercises()],
    )


# ------------------------------------------------- adaptive prescription
# Physically-trainable weak aspects from the Video Analysis skill ledger ->
# a corrective exercise. Only aspects off-table training can actually address.
_PRESCRIPTION_MAP = {
    "stance_posture": ("side_plank", "posture / stance"),
    "footwork": ("lateral_toe_steps", "footwork"),
    "physical": ("plank", "fitness / core"),
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
    reason = f"Video shows {aspect_label} is still weak"
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


def _ensure_daily(db: Session, session: TrainingSession) -> None:
    """Append the daily exercises to the open session (once each).

    Daily = the fixed staples (powerball, thigh-over-bottle) + today's rotating
    1kg-dumbbell picks. Mirrors `_apply_prescription`: idempotent, runs on the
    open session so even a session materialised before these existed picks them
    up. Each carries its own progressive target (ramps with training age +
    autoregulation bias). Placed before the prescription so the order is
    [program, daily, prescribed].
    """
    if session.status == "done":
        return
    state = ensure_state(db)
    bias = state.intensity_bias or 0
    gday = program.global_day_number(session.level, session.day_index)
    existing = {it.exercise_key for it in session.items}
    missing = [ex for ex in program.daily_for(gday) if ex.key not in existing]
    if not missing:
        return
    max_order = max((it.sort_order for it in session.items), default=-1)
    for ex in missing:
        max_order += 1
        session.items.append(
            TrainingSessionItem(
                exercise_key=ex.key,
                target_json=json.dumps(program.daily_target(ex, gday, bias)),
                sort_order=max_order,
            )
        )
    db.commit()
    db.refresh(session)


def get_today(db: Session) -> schemas.SessionOut:
    session, _ = open_session(db)
    _ensure_daily(db, session)
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


def substitute_item(
    db: Session, session_id: int, item_id: int, new_key: str
) -> schemas.SessionOut | None:
    """Swap an exercise for a knee-safe alternative (e.g. the original hurt)."""
    item = db.get(TrainingSessionItem, item_id)
    if item is None or item.session_id != session_id:
        return None
    ex = program.EXERCISES.get(new_key)
    if ex is None:
        return None
    state = ensure_state(db)
    session = db.get(TrainingSession, session_id)
    # Only accept a key actually offered for this item (same alternatives the
    # GUI shows) — not any arbitrary exercise (e.g. a warm-up move).
    in_session = {it.exercise_key for it in session.items} if session else set()
    offered = {a.key for a in program.alternatives_for(item.exercise_key, in_session)}
    if new_key not in offered:
        return None
    cycle = (
        program.cycle_of(session.day_index)
        if session and session.level == program.MAINTENANCE_LEVEL
        else 0
    )
    item.exercise_key = new_key
    item.target_json = json.dumps(program.scaled_target(ex, cycle, state.intensity_bias or 0))
    item.done = False
    item.skipped = False
    db.commit()
    return to_session_out(session) if session else None


def skip_item(
    db: Session, session_id: int, item_id: int, skipped: bool
) -> schemas.SessionOut | None:
    """Mark an exercise skipped (logged — e.g. it aggravated the knee)."""
    item = db.get(TrainingSessionItem, item_id)
    if item is None or item.session_id != session_id:
        return None
    item.skipped = skipped
    if skipped:
        item.done = False
    db.commit()
    session = db.get(TrainingSession, session_id)
    return to_session_out(session) if session else None


def _autoregulate(db: Session, pain: str | None, rpe: str | None) -> None:
    """Nudge the intensity bias from this session's feedback (next sessions react).

    Pain is the safety brake; RPE fine-tunes. Clamped to a sane band.
    """
    state = ensure_state(db)
    delta = 0
    if pain == "strong":
        delta = -2
    elif pain == "mild":
        delta = -1
    elif rpe == "easy":  # only push up when it was easy AND pain-free
        delta = 1
    elif rpe == "hard":
        delta = 0  # hard but no pain = good stimulus; hold, don't add
    state.intensity_bias = max(-2, min((state.intensity_bias or 0) + delta, 3))
    db.commit()


def complete_session(
    db: Session,
    level: str,
    day_index: int,
    note: str | None,
    pain: str | None = None,
    rpe: str | None = None,
    done_on: dt.date | None = None,
) -> schemas.SessionOut:
    """Mark a session done, stamp the date, record feedback + autoregulate.

    ``done_on`` lets the user backdate a session trained earlier but logged
    later (e.g. trained yesterday, ticked today). Defaults to today; a future
    date is clamped to today.
    """
    if level not in program.LEVELS or day_index < 1:
        raise ValueError(f"No such session ({level}, {day_index}).")
    today = dt.date.today()
    when = done_on if (done_on is not None and done_on <= today) else today
    session = _materialise(db, level, day_index)
    session.status = "done"
    session.done_on = when
    # Keep completed_at consistent with the trained date: now() if it's today,
    # else end-of-day on the backdated date (it's only a record, not used in logic).
    session.completed_at = (
        dt.datetime.now() if when == today
        else dt.datetime.combine(when, dt.time(23, 59))
    )
    if note is not None:
        session.note = note
    session.pain = pain
    session.rpe = rpe
    # Count only non-skipped exercises toward the session duration.
    exs = [program.EXERCISES[it.exercise_key] for it in session.items
           if it.exercise_key in program.EXERCISES and not it.skipped]
    session.duration_min = program.estimate_minutes(exs)
    db.commit()
    _autoregulate(db, pain, rpe)
    db.refresh(session)
    return to_session_out(session)


# ---------------------------------------------------------------- grid / levels
def program_grid(db: Session, level: str | None = None) -> schemas.ProgramOut:
    state = ensure_state(db)
    level = level or state.current_level
    done = _done_count(db, level)
    n = program.SESSIONS_PER_LEVEL

    # The top level is endless: it repeats in cycles with progressive
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
        cycle=cycle + 1,  # 1-based "Cycle N"
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
        .options(selectinload(TrainingSession.items))  # avoid per-session lazy loads
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
            "No sessions recently. Start again with today's session — "
            "consistency matters more than intensity."
        )
    if days_since is not None and days_since >= 4:
        return (
            f"It's been {days_since} days without training. Get back to it today — "
            "the training only works if you keep the rhythm."
        )
    if last7 >= 5:
        return f"{last7} sessions this week — good rhythm at {level_vi} level. Keep it up."
    if last7 >= 3:
        return f"{last7} sessions this week. Decent — push a bit more to hit 5 sessions/week."
    return f"Only {last7} sessions this week. Be more consistent — target 5 sessions/week."


def report(db: Session) -> schemas.ReportOut:
    """Tier-1 brain view for the Head Coach: training load, adherence, volume."""
    state = ensure_state(db)
    today = dt.date.today()
    # All-time total via COUNT; the detailed scan (items, streak, volume) is
    # floored to the last year so cost stays flat as history grows.
    total_done = (
        db.query(TrainingSession)
        .filter(TrainingSession.status == "done", TrainingSession.done_on.isnot(None))
        .count()
    )
    floor = today - dt.timedelta(days=365)
    done = (
        db.query(TrainingSession)
        .options(selectinload(TrainingSession.items))  # avoid per-session lazy loads
        .filter(
            TrainingSession.status == "done",
            TrainingSession.done_on.isnot(None),
            TrainingSession.done_on >= floor,
        )
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
    # Distinct completed dates (most recent first) → heatmap + current streak.
    done_dates_desc = sorted({s.done_on for s in done}, reverse=True)
    streak = 0
    cursor = today
    date_set = set(done_dates_desc)
    # A streak counts back from today; if today isn't trained yet, allow it to
    # start from yesterday (so an unbroken run isn't "lost" before today's session).
    if today not in date_set and (today - dt.timedelta(days=1)) in date_set:
        cursor = today - dt.timedelta(days=1)
    while cursor in date_set:
        streak += 1
        cursor -= dt.timedelta(days=1)

    level_vi = program.LEVEL_VI.get(state.current_level, state.current_level)
    return schemas.ReportOut(
        current_level=state.current_level,
        current_level_vi=level_vi,
        cutover_date=state.cutover_date,
        total_sessions_done=total_done,
        sessions_last_7d=last7,
        sessions_last_30d=last30,
        last_session_date=last_date,
        days_since_last=days_since,
        day_type_counts=day_type_counts,
        muscle_volume=muscle_volume,
        levels=level_overview(db).levels,
        recent=recent,
        summary_vi=_weekly_summary(last7, last30, days_since, level_vi),
        current_streak=streak,
        done_dates=[d for d in done_dates_desc if (today - d).days < 70],
        intensity_bias=state.intensity_bias or 0,
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
