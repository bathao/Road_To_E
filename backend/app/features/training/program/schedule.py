"""Which exercises a (level, day) session contains, and its duration estimate.

Part of the static programme package (split 2026-10-16 from program.py;
see REFACTOR.md §4.2). Import names via ``app.features.training.program``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import EXERCISES, Exercise
from .levels import DAY_CYCLE, DAY_FOCUS_VI

# Per-level, per-day-type session templates (3–4 exercises each). Progression is
# by harder variants + more volume, never by adding impact.
DAY_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "foundation": {
        # Quad-first: quad/hip work; gentle intro of upper body on the balance day.
        "legs": ["quad_set", "straight_leg_raise", "short_arc_quad", "side_leg_raise",
                 "lateral_lunge"],
        "core": ["plank", "double_leg_lift_hold", "standing_trunk_twist", "crunch"],
        "balance": ["single_leg_balance", "wall_pushup", "wrist_curl", "thoracic_rotation"],
    },
    "explosive": {
        # Quad-led + posterior chain (hip hinge); core adds anti-rotation; upper body grows.
        "legs": ["short_arc_quad", "lateral_lunge", "glute_bridge", "wall_sit_shallow",
                 "hip_hinge"],
        "core": ["plank_shoulder_tap", "bird_dog", "plank_knee_rotation",
                 "standing_trunk_twist", "side_plank"],
        "balance": ["single_leg_balance", "wall_pushup", "scapular_yt", "wrist_curl",
                    "gentle_bounce"],
    },
    "tt_specific": {
        # Functional quad/hip + posterior chain + low-impact footwork; rotation-power core;
        # advanced balance + shoulder/wrist/mobility.
        "legs": ["short_arc_quad", "single_leg_glute_bridge", "lateral_lunge",
                 "lateral_toe_steps", "hip_hinge"],
        "core": ["russian_twist", "wood_chop", "plank_knee_rotation", "plank_shoulder_tap",
                 "standing_trunk_twist"],
        "balance": ["single_leg_eyes_closed", "scapular_yt", "wrist_curl",
                    "thoracic_rotation", "gentle_bounce"],
    },
}


def day_type_for(day_index: int) -> str:
    """The day-type of session `day_index` (1-based) via the micro-cycle."""
    return DAY_CYCLE[(day_index - 1) % len(DAY_CYCLE)]


def exercises_for(day_type: str, level: str) -> list[Exercise]:
    """The exercises of a session, from the per-level day template."""
    keys = DAY_TEMPLATES.get(level, {}).get(day_type, [])
    return [EXERCISES[k] for k in keys if k in EXERCISES]


@dataclass
class PlannedSession:
    level: str
    day_index: int
    day_type: str
    focus_vi: str
    exercises: list[Exercise] = field(default_factory=list)


def planned_session(level: str, day_index: int) -> PlannedSession:
    """Build the (static) prescription for one session of a level."""
    day_type = day_type_for(day_index)
    return PlannedSession(
        level=level,
        day_index=day_index,
        day_type=day_type,
        focus_vi=DAY_FOCUS_VI[day_type],
        exercises=exercises_for(day_type, level),
    )


def estimate_minutes(exs: list[Exercise]) -> int:
    """Rough session duration estimate (for the header), minutes."""
    secs = 0
    for e in exs:
        sets = e.target.get("sets", 1)
        sides = 2 if e.per_side else 1
        if e.kind == "timed":
            work = e.target.get("sec", 30)
        else:
            work = e.target.get("reps", 15) * 2  # ~2s per rep
        secs += sets * sides * work + sets * 20  # +20s rest between sets
    return max(1, round(secs / 60))
