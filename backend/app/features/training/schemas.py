"""Pydantic request/response models for the Training Center tab."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class ItemAlt(BaseModel):
    key: str
    name_vi: str


class SimpleExercise(BaseModel):
    """Warm-up / cool-down move — shown but not tracked or counted."""

    exercise_key: str
    name_vi: str
    muscle: str
    tt_benefit: str
    kind: str
    target: dict
    per_side: bool
    gif: str
    form_cue: str
    how_to: list[str] = []


class ItemOut(BaseModel):
    id: int
    exercise_key: str
    name_vi: str
    muscle: str
    tt_benefit: str
    kind: str  # reps | timed
    target: dict  # {"sets":3,"reps":20} or {"sets":3,"sec":45}
    per_side: bool
    gif: str
    form_cue: str
    how_to: list[str] = []
    done: bool
    is_prescribed: bool
    rx_reason: str | None = None
    skipped: bool = False
    alternatives: list[ItemAlt] = []


class SessionOut(BaseModel):
    id: int
    level: str
    level_vi: str
    day_index: int
    day_type: str
    focus_vi: str
    est_minutes: int
    status: str  # unlocked | done
    done_count: int  # items ticked
    total: int  # items in the session
    progress_pct: int  # 0..100 over items
    done_on: dt.date | None = None
    note: str | None = None
    pain: str | None = None  # none | mild | strong
    rpe: str | None = None  # easy | medium | hard
    items: list[ItemOut] = []
    warmup: list[SimpleExercise] = []  # gentle knee mobility before (not tracked)
    cooldown: list[SimpleExercise] = []  # stretches after (not tracked)


class TileOut(BaseModel):
    """One "Day" tile in the level grid (BetterMe-style)."""

    day_index: int
    day_type: str
    focus_vi: str
    status: str  # done | unlocked | locked
    thumb: str  # gif of the session's first exercise


class ProgramOut(BaseModel):
    level: str
    level_vi: str
    goal_vi: str
    safety_note: str  # knee-safety reminder shown in the header
    cycle: int  # 1-based maintenance cycle ("Cycle N"); 1 for finite levels
    total_sessions: int
    completed: int  # sessions done in the current cycle
    progress_pct: int
    tiles: list[TileOut]


class LevelInfo(BaseModel):
    key: str
    label_vi: str
    goal_vi: str
    unlocked: bool
    completed: int  # sessions done at this level
    total: int


class LevelOut(BaseModel):
    current_level: str
    levels: list[LevelInfo]


class TickIn(BaseModel):
    done: bool


class CompleteIn(BaseModel):
    note: str | None = None
    pain: str | None = None  # none | mild | strong — drives autoregulation + safety
    rpe: str | None = None  # easy | medium | hard
    # The date the session was actually trained. Defaults to today; can be
    # backdated (e.g. trained yesterday, logged today). Never in the future.
    done_on: dt.date | None = None


class SubstituteIn(BaseModel):
    exercise_key: str  # the alternative to swap in


class SkipIn(BaseModel):
    skipped: bool


# ---------- Report (Tier-1 "brain view" the Head Coach reads) ----------
class MuscleVolume(BaseModel):
    muscle: str
    times: int  # how many exercise-instances of this muscle group were done


class RecentSession(BaseModel):
    done_on: dt.date
    level: str
    day_index: int
    focus_vi: str
    done_count: int
    total: int


class ReportOut(BaseModel):
    current_level: str
    current_level_vi: str
    cutover_date: dt.date | None
    total_sessions_done: int
    sessions_last_7d: int
    sessions_last_30d: int
    last_session_date: dt.date | None
    days_since_last: int | None
    day_type_counts: dict[str, int]  # legs/core/balance -> sessions done
    muscle_volume: list[MuscleVolume]
    levels: list[LevelInfo]
    recent: list[RecentSession]
    summary_vi: str  # short coach-voice weekly summary, data-driven
    current_streak: int  # consecutive days (up to today) with a completed session
    done_dates: list[dt.date]  # recent completed-session dates (for the heatmap)
    intensity_bias: int  # current autoregulation adjustment (±)
