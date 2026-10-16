"""Progressive overload on the maintenance level + knee-safe substitutes.

Part of the static programme package (split 2026-10-16 from program.py;
see REFACTOR.md §4.2). Import names via ``app.features.training.program``.
"""
from __future__ import annotations

from .catalog import _EX, COOLDOWN_KEYS, EXERCISES, WARMUP_KEYS, Exercise
from .daily import _DAILY_WORK_KEYS, NO_SWAP_KEYS

OVERLOAD_MAX_CYCLES = 3  # overload stops growing after this many maintenance cycles


OVERLOAD_BUMP_CAP = OVERLOAD_MAX_CYCLES + 2  # autoregulation can push a bit past


OVERLOAD_BUMP_SEC = 5   # +5s per step for timed holds


OVERLOAD_BUMP_REPS = 2  # +2 reps per step for rep work


def scaled_target(ex: Exercise, cycle: int, bias: int = 0) -> dict:
    """Apply progressive overload + autoregulation to an exercise's target.

    Base overload = min(cycle, OVERLOAD_MAX_CYCLES). `bias` is the autoregulation
    adjustment from recent pain/RPE feedback (easy → +, hard/pain → −). The
    effective bump is clamped to [0, OVERLOAD_BUMP_CAP]; each step adds
    OVERLOAD_BUMP_SEC to timed holds or OVERLOAD_BUMP_REPS to rep work. Sets
    never change; knee-safe by design.
    """
    base = min(max(cycle, 0), OVERLOAD_MAX_CYCLES)
    bump = max(0, min(base + bias, OVERLOAD_BUMP_CAP))
    if bump == 0:
        return dict(ex.target)
    t = dict(ex.target)
    if ex.kind == "timed" and "sec" in t:
        t["sec"] = t["sec"] + OVERLOAD_BUMP_SEC * bump
    elif "reps" in t:
        t["reps"] = t["reps"] + OVERLOAD_BUMP_REPS * bump
    return t


def alternatives_for(key: str, exclude: set[str]) -> list[Exercise]:
    """Knee-safe substitutes for a PROGRAMME exercise: same day-type, not
    already in the session, never warm-up/cool-down or daily work. Empty for
    daily items themselves. Used by the "swap if it hurts" substitution."""
    ex = EXERCISES.get(key)
    if ex is None or key in _DAILY_WORK_KEYS:
        return []
    out = [
        e for e in _EX
        if e.day_type == ex.day_type and e.key != key and e.key not in exclude
        # Warmup/cooldown moves aren't tracked work — the cooldown stretches
        # share day_type "balance", so without this they'd crowd the top of
        # a balance-day substitution list.
        and e.key not in WARMUP_KEYS and e.key not in COOLDOWN_KEYS
        and e.key not in NO_SWAP_KEYS and e.key not in _DAILY_WORK_KEYS
    ]
    return out[:3]
