"""Static program reference for the Training Center.

This module is the single source of truth for *what* a session contains. The DB
(models.py) only stores the player's progress through these programs. Nothing
here is persisted, so editing it changes future sessions without a migration.

KNEE-SAFE curriculum. The player has grade-1 knee osteoarthritis, so this program
deliberately AVOIDS deep squats, lunges, and jumping/plyometrics. It builds the
muscles around the knee (quads via leg raises, glutes/hips, hamstrings, calves)
and the rotational core, using low-load, low-impact home exercises. "Progression"
across levels = more reps/holds + slightly harder variants, NOT more impact.
The one impact exception is jump rope (2026-09-05): the player skips rope daily
on the real coach's footwork advice, so it rides along as a DAILY staple item
(fixed 100+ jumps = done, never ramped, never offered as a knee-safe swap).

A package since 2026-10-16: levels · catalog · daily · how_to · schedule ·
progression. Everything is re-exported here so ``program.X`` keeps working.
"""
from __future__ import annotations

from .catalog import (  # noqa: F401
    _EX,
    COOLDOWN_KEYS,
    EXERCISES,
    WARMUP_KEYS,
    Exercise,
    _gif,
    cooldown_exercises,
    warmup_exercises,
)
from .daily import (  # noqa: F401
    _DAILY_WORK_KEYS,
    DAILY_BUMP_REPS,
    DAILY_BUMP_SEC,
    DAILY_KEYS,
    DAILY_STEP_CAP,
    DAILY_STEP_DAYS,
    DUMBBELL_KEYS,
    DUMBBELL_PER_DAY,
    NO_RAMP_KEYS,
    NO_SWAP_KEYS,
    daily_dumbbells,
    daily_exercises,
    daily_for,
    daily_target,
    global_day_number,
)
from .how_to import (  # noqa: F401
    HOW_TO,
    how_to_for,
)
from .levels import (  # noqa: F401
    DAY_CYCLE,
    DAY_FOCUS_VI,
    DAY_TYPES,
    LEVEL_GOAL_VI,
    LEVEL_VI,
    LEVELS,
    MAINTENANCE_LEVEL,
    SAFETY_NOTE_VI,
    SESSIONS_PER_LEVEL,
    cycle_of,
    next_level,
)
from .progression import (  # noqa: F401
    OVERLOAD_BUMP_CAP,
    OVERLOAD_BUMP_REPS,
    OVERLOAD_BUMP_SEC,
    OVERLOAD_MAX_CYCLES,
    alternatives_for,
    scaled_target,
)
from .schedule import (  # noqa: F401
    DAY_TEMPLATES,
    PlannedSession,
    day_type_for,
    estimate_minutes,
    exercises_for,
    planned_session,
)
