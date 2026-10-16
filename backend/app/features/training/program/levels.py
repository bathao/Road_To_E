"""Levels, day types and the per-level session count (the programme's skeleton).

Part of the static programme package (split 2026-10-16 from program.py;
see REFACTOR.md §4.2). Import names via ``app.features.training.program``.
"""
from __future__ import annotations

# Shown under the header so the player is reminded of the knee constraint.
SAFETY_NOTE_VI = (
    "Prioritize the THIGH MUSCLES to take load off the knee joint (doctor's advice). "
    "No deep squats / lunges / hard jumping. The light quad work (quad sets, leg raises, "
    "short-arc) can be done daily. Stop immediately if the knee hurts. "
    "Jump rope (your own daily add-on, coach-requested footwork) is the ONE impact "
    "exception: low bounce, soft landing — skip it the moment the knee complains."
)


# Day-types a session focuses on + the focus label shown in the header.
DAY_TYPES = ("legs", "core", "balance")


DAY_FOCUS_VI = {
    "legs": "Quads (priority) — strong thighs take load off the knee",
    "core": "Core: rotation & anti-rotation",
    "balance": "Balance · shoulders · wrists (TT support work, knee-gentle)",
}


# A 6-session micro-cycle that PRIORITISES quads: legs 3/6, core 2/6, balance 1/6.
# Quad-strengthening is the evidence-based priority for knee OA, so leg days come
# up every other session.
DAY_CYCLE = ("legs", "core", "legs", "balance", "legs", "core")


# Levels, in unlock order.
LEVELS = ("foundation", "explosive", "tt_specific")


LEVEL_VI = {
    "foundation": "Foundation",
    "explosive": "Endurance & Stability",
    "tt_specific": "TT-Specific (knee-friendly)",
}


LEVEL_GOAL_VI = {
    "foundation": "Activate quads/glutes/hips WITHOUT deep knee loading; get used to holding a stable base.",
    "explosive": "Build endurance in the muscles around the knee + core stability, still easy on the joint.",
    "tt_specific": "Simulate table-tennis movement at moderate intensity, low-impact, knee-protective.",
}


# Number of sessions ("Day" tiles) per level.
SESSIONS_PER_LEVEL = 21


def next_level(level: str) -> str | None:
    """The level after `level`, or None if it is the last one."""
    i = LEVELS.index(level)
    return LEVELS[i + 1] if i + 1 < len(LEVELS) else None


# --------------------------------------------------- maintenance / progression
# After the last level is finished the program does NOT dead-end: it repeats the
# top (sport-specific) level in "cycles" with gentle progressive overload.
# Overload plateaus after a few cycles — for a knee-OA client we add time-under-
# tension / reps, never load or impact, and we cap it so it stays sensible. The
# Head Coach (Tier-2) is meant to take over the "what next" eventually.
MAINTENANCE_LEVEL = LEVELS[-1]  # the endless top level (tt_specific)


def cycle_of(day_index: int) -> int:
    """0-based cycle a (1-based) session index falls in. 1..21 -> 0, 22..42 -> 1…"""
    return (day_index - 1) // SESSIONS_PER_LEVEL
