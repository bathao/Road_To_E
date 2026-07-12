"""Static program math: maintenance cycles and the global training-age number."""
from __future__ import annotations

from app.features.training import program


def test_maintenance_cycle_and_global_day_consistency():
    n = program.SESSIONS_PER_LEVEL
    assert n == 21
    assert program.LEVELS == ("foundation", "explosive", "tt_specific")
    assert program.MAINTENANCE_LEVEL == program.LEVELS[-1]

    # cycle_of: 1..21 -> 0, 22..42 -> 1, 43 -> 2 (maintenance repeats forever).
    assert program.cycle_of(1) == 0
    assert program.cycle_of(n) == 0
    assert program.cycle_of(n + 1) == 1
    assert program.cycle_of(2 * n) == 1
    assert program.cycle_of(2 * n + 1) == 2

    # global_day_number never resets between levels.
    assert program.global_day_number("foundation", 1) == 1
    assert program.global_day_number("foundation", n) == n
    assert program.global_day_number("explosive", 1) == n + 1
    assert program.global_day_number(program.MAINTENANCE_LEVEL, 1) == 2 * n + 1

    # Consistency on the maintenance level: absolute day_index d in cycle c
    # maps to global day 2*n + d, and c == cycle_of(d).
    for cycle in range(3):
        d = cycle * n + 5  # 5th session of each maintenance cycle
        assert program.cycle_of(d) == cycle
        assert program.global_day_number(program.MAINTENANCE_LEVEL, d) == 2 * n + d

    # Unknown level falls back to base 0 rather than crashing.
    assert program.global_day_number("bogus", 7) == 7
