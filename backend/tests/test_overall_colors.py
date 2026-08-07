"""compute_overall_colors: the auto-generated 'Overall' row (pure function).

User rule 2026-08-04: green = racket time >= 60p that day (coach/partner
training + sets × 5p, the Racket Time row's number); yellow = anything logged
but under the bar (short racket day, physical, other rows); red = tracked
past day with nothing at all. The grid measures quantity — quality is ELO's.
"""
from __future__ import annotations

import datetime as dt

from app.features.tracker.service import compute_overall_colors
from app.features.tracker.models import Activity, Category, Match

D0 = dt.date(2026, 7, 6)  # earliest tracked day
D1 = dt.date(2026, 7, 7)
D2 = dt.date(2026, 7, 8)
D3 = dt.date(2026, 7, 9)  # "today" for these tests

COACH_CAT = Category(id=1, key="train_with_coach", label="", type="duration",
                     color_group="green", sort_order=0)
# Deliberately green-group: proves color_group no longer drives Overall —
# serve practice is purposeful but it is NOT racket time.
SERVE_CAT = Category(id=2, key="serve_practice", label="", type="duration",
                     color_group="green", sort_order=1)
CATEGORIES = [COACH_CAT, SERVE_CAT]


def _bo5(date: dt.date, n: int) -> list[Match]:
    """n played BO5 sweeps = n × 3 sets × 5p of racket time."""
    return [
        Match(date=date, my_sets=3, opp_sets=0, is_nonplaying=False)
        for _ in range(n)
    ]


def test_hour_of_racket_time_is_green_less_is_yellow():
    activities = [
        # D0: exactly one standard 1h coach session → green (>=, not >).
        Activity(date=D0, category_id=COACH_CAT.id, duration_minutes=60),
        # D1: 30p with the coach → logged, but under the bar → yellow.
        Activity(date=D1, category_id=COACH_CAT.id, duration_minutes=30),
    ]
    colors = compute_overall_colors(
        CATEGORIES, activities, matches=[],
        physical_dates=set(), all_days=[D0, D1], today=D3, earliest=D0,
    )
    assert colors[D0.isoformat()] == "green"
    assert colors[D1.isoformat()] == "yellow"


def test_match_only_sparring_day_can_go_green():
    # 4 played BO5 matches = 12 sets = 60p → green (the old rule could never
    # turn a match-only day green); 2 matches = 30p → yellow.
    colors = compute_overall_colors(
        CATEGORIES, [], _bo5(D0, 4) + _bo5(D1, 2),
        physical_dates=set(), all_days=[D0, D1], today=D3, earliest=D0,
    )
    assert colors[D0.isoformat()] == "green"
    assert colors[D1.isoformat()] == "yellow"


def test_training_and_matches_sum_toward_the_hour():
    activities = [Activity(date=D0, category_id=COACH_CAT.id, duration_minutes=30)]
    matches = [Match(date=D0, my_sets=3, opp_sets=3, is_nonplaying=False)]  # 30p
    colors = compute_overall_colors(
        CATEGORIES, activities, matches,
        physical_dates=set(), all_days=[D0], today=D3, earliest=D0,
    )
    assert colors[D0.isoformat()] == "green"


def test_non_racket_data_is_yellow_and_empty_past_is_red():
    activities = [
        # D0: 90p of serve practice — deliberate, but not racket time.
        Activity(date=D0, category_id=SERVE_CAT.id, duration_minutes=90),
        # D2: zero-duration entry must NOT count as data (day stays empty).
        Activity(date=D2, category_id=COACH_CAT.id, duration_minutes=0),
    ]
    colors = compute_overall_colors(
        CATEGORIES, activities, matches=[],
        physical_dates={D1.isoformat()},  # D1: physical only → yellow
        all_days=[D0, D1, D2, D3], today=D3, earliest=D0,
    )
    assert colors[D0.isoformat()] == "yellow"
    assert colors[D1.isoformat()] == "yellow"
    # D2 is a past, empty day within the tracked range → red.
    assert colors[D2.isoformat()] == "red"
    # D3 is today: no data yet, but not red (day isn't over).
    assert D3.isoformat() not in colors


def test_legacy_travel_rest_rows_stay_yellow():
    # The entry buttons are gone (2026-08-04) but old rows are data — a
    # logged Travel day is not "nothing", so it must never turn red.
    m = Match(date=D0, my_sets=0, opp_sets=0, is_nonplaying=True,
              nonplaying_label="Travel")
    colors = compute_overall_colors(
        CATEGORIES, [], [m],
        physical_dates=set(), all_days=[D0], today=D3, earliest=D0,
    )
    assert colors[D0.isoformat()] == "yellow"


def test_days_before_tracking_began_stay_uncolored():
    before = D0 - dt.timedelta(days=1)
    colors = compute_overall_colors(
        CATEGORIES,
        [Activity(date=D0, category_id=COACH_CAT.id, duration_minutes=60)],
        matches=[],
        physical_dates=set(),
        all_days=[before, D0],
        today=D3,
        earliest=D0,
    )
    assert before.isoformat() not in colors  # not red: tracking hadn't begun
    assert colors[D0.isoformat()] == "green"
