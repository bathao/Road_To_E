"""compute_overall_colors: the auto-generated 'Overall' row (pure function)."""
from __future__ import annotations

import datetime as dt

from app.features.tracker.service import compute_overall_colors
from app.features.tracker.models import Activity, Category, Match

D0 = dt.date(2026, 7, 6)  # earliest tracked day
D1 = dt.date(2026, 7, 7)
D2 = dt.date(2026, 7, 8)
D3 = dt.date(2026, 7, 9)  # "today" for these tests

GREEN_CAT = Category(id=1, key="train_with_coach", label="", type="duration",
                     color_group="green", sort_order=0)
OTHER_CAT = Category(id=2, key="serve_x", label="", type="duration",
                     color_group="none", sort_order=1)
CATEGORIES = [GREEN_CAT, OTHER_CAT]


def test_green_yellow_red_and_absent():
    activities = [
        # D0: green-group activity with duration -> green
        Activity(date=D0, category_id=GREEN_CAT.id, duration_minutes=60),
        # D2: zero-duration entry must NOT count as data (day stays empty)
        Activity(date=D2, category_id=GREEN_CAT.id, duration_minutes=0),
    ]
    colors = compute_overall_colors(
        CATEGORIES,
        activities,
        matches=[],
        physical_dates={D1.isoformat()},  # D1: physical only -> yellow
        all_days=[D0, D1, D2, D3],
        today=D3,
        earliest=D0,
    )
    assert colors[D0.isoformat()] == "green"
    assert colors[D1.isoformat()] == "yellow"
    # D2 is a past, empty day within the tracked range -> red.
    assert colors[D2.isoformat()] == "red"
    # D3 is today: no data yet, but not red (day isn't over).
    assert D3.isoformat() not in colors


def test_green_wins_over_yellow_and_matches_count_as_yellow():
    activities = [
        Activity(date=D0, category_id=GREEN_CAT.id, duration_minutes=30),
        Activity(date=D0, category_id=OTHER_CAT.id, duration_minutes=30),
    ]
    matches = [Match(date=D1)]  # any match entry marks the day as activity
    colors = compute_overall_colors(
        CATEGORIES, activities, matches,
        physical_dates=set(), all_days=[D0, D1], today=D3, earliest=D0,
    )
    assert colors[D0.isoformat()] == "green"  # green trumps the yellow signal
    assert colors[D1.isoformat()] == "yellow"


def test_days_before_tracking_began_stay_uncolored():
    before = D0 - dt.timedelta(days=1)
    colors = compute_overall_colors(
        CATEGORIES,
        [Activity(date=D0, category_id=GREEN_CAT.id, duration_minutes=60)],
        matches=[],
        physical_dates=set(),
        all_days=[before, D0],
        today=D3,
        earliest=D0,
    )
    assert before.isoformat() not in colors  # not red: tracking hadn't begun
    assert colors[D0.isoformat()] == "green"
