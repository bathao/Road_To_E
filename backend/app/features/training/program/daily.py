"""Daily work appended to every session: staples, the rotating dumbbell picks, their ramp.

Part of the static programme package (split 2026-10-16 from program.py;
see REFACTOR.md §4.2). Import names via ``app.features.training.program``.
"""
from __future__ import annotations

from .catalog import EXERCISES, Exercise
from .levels import LEVELS, SESSIONS_PER_LEVEL

# Exercises appended to EVERY session (the player asked to train these daily):
# the wrist powerball, the supine hip/core "thigh-over-bottle" and (2026-09-05)
# jump rope. Unlike the warm-up these ARE tracked and counted, and they carry
# their own progressive ramp (daily_target) instead of the level/day-type
# rotation — except the NO_RAMP_KEYS, whose target is the user's fixed rule.
DAILY_KEYS = ("gyro_ball", "thigh_lift_bottle", "jump_rope")


# Daily staples whose target never ramps (jump rope: "100+ a day = done").
NO_RAMP_KEYS = ("jump_rope",)


# Never offered by alternatives_for as a "knee-safe" swap — the one impact move.
NO_SWAP_KEYS = ("jump_rope",)


# 1kg-dumbbell pool. The player trains with weights daily, but doing all of these
# every day would overload the shoulders and bloat the session, so we ROTATE: a
# different DUMBBELL_PER_DAY of them each day (~a 5-day cycle through the 10). The
# order interleaves shoulder/back work with core/rotation and the seated weighted-
# abs compounds so each day is balanced. Intensity still ramps via daily_target
# (reps), so "usage changes day to day AND load progresses week to week".
DUMBBELL_KEYS = (
    "db_trunk_twist",         # core / rotation
    "db_shoulder_press",      # shoulder
    "db_seated_leg_press",    # seated weighted abs (core + thigh + arm)
    "db_lateral_raise",       # shoulder
    "db_wood_chop",           # core / diagonal rotation
    "db_seated_overhead_tuck",  # seated weighted abs (core + thigh + shoulder)
    "db_shadow_swing",        # TT-specific shoulder/arm
    "db_seated_leg_spread",   # seated weighted abs (core + thigh + shoulder)
    "db_bent_row",            # upper back / posture
    "db_seated_pass_under",   # seated weighted abs (core + thigh + arm)
)


DUMBBELL_PER_DAY = 2


def daily_exercises() -> list[Exercise]:
    return [EXERCISES[k] for k in DAILY_KEYS if k in EXERCISES]


def daily_dumbbells(global_day: int) -> list[Exercise]:
    """The DUMBBELL_PER_DAY weighted exercises for this training day.

    Deterministic in `global_day` (so it's stable/idempotent per session): walks
    the pool DUMBBELL_PER_DAY at a time, wrapping around — different bias of the
    body each day, full pool covered every few days."""
    n = len(DUMBBELL_KEYS)
    if n == 0:
        return []
    take = min(DUMBBELL_PER_DAY, n)
    start = ((max(global_day, 1) - 1) * take) % n
    keys = [DUMBBELL_KEYS[(start + i) % n] for i in range(take)]
    return [EXERCISES[k] for k in keys if k in EXERCISES]


def daily_for(global_day: int) -> list[Exercise]:
    """All exercises that should be appended to a session at this training age:
    the fixed daily staples + today's rotating dumbbell picks."""
    return daily_exercises() + daily_dumbbells(global_day)


# --------------------------------------------------- daily-staple progression
# The daily exercises are done from day 1 and must ramp on the FINITE levels too
# (the level/cycle overload above only kicks in on the endless maintenance level).
# We drive their intensity off a monotonic "training-age" day number that never
# resets between levels, bumping ~weekly and capping so it stays knee/tendon-safe.
DAILY_STEP_DAYS = 7   # advance one intensity step roughly every week of daily work


DAILY_STEP_CAP = 5    # stop ramping after this many steps (sensible ceiling)


DAILY_BUMP_SEC = 8    # +8s per step for timed holds (20s → 60s at the cap)


DAILY_BUMP_REPS = 2   # +2 reps per step for rep work (8 → 18 at the cap)


def global_day_number(level: str, day_index: int) -> int:
    """A monotonic session number across all levels (never resets between them).

    Foundation 1..21 → 1..21, Explosive → 22..42, the top/maintenance level →
    43+ (its day_index already keeps growing across cycles). Used only to pace
    the daily staples, so they keep getting harder regardless of level."""
    try:
        base = LEVELS.index(level) * SESSIONS_PER_LEVEL
    except ValueError:
        base = 0
    return base + day_index


def daily_target(ex: Exercise, global_day: int, bias: int = 0) -> dict:
    """Progressive target for a daily-staple exercise at a given training age.

    Steps up ~weekly (capped), then `bias` applies the same pain/RPE
    autoregulation as the rest of the program (hard/pain → ease off)."""
    t = dict(ex.target)
    if ex.key in NO_RAMP_KEYS:
        return t  # fixed by the user's rule, not by training age
    step = min(max(global_day - 1, 0) // DAILY_STEP_DAYS, DAILY_STEP_CAP)
    step = max(0, min(step + bias, DAILY_STEP_CAP + 2))
    if step == 0:
        return t
    if ex.kind == "timed" and "sec" in t:
        t["sec"] = t["sec"] + DAILY_BUMP_SEC * step
    elif "reps" in t:
        t["reps"] = t["reps"] + DAILY_BUMP_REPS * step
    return t


# Daily work is never part of a swap, in either direction: the staples are
# appended to EVERY session by the service (a swapped-away staple would simply
# re-appear next to its substitute on the next read), and the dumbbell pool
# rotates on its own schedule. A staple that hurts is skipped, not swapped.
_DAILY_WORK_KEYS = frozenset(DAILY_KEYS) | frozenset(DUMBBELL_KEYS)
