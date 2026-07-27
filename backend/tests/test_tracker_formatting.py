"""Pure formatting helpers of the tracker service (no DB needed)."""
from __future__ import annotations

import datetime as dt

from app.features.tracker import service
from app.features.tracker.models import Event, Match


def test_format_duration():
    assert service.format_duration(0) == ""
    assert service.format_duration(45) == "45 mins"
    assert service.format_duration(60) == "1 hour"
    assert service.format_duration(90) == "1 hour 30 mins"
    assert service.format_duration(120) == "2 hour"


def test_result_letter():
    assert service._result_letter(3, 1) == "W"
    assert service._result_letter(1, 3) == "L"
    assert service._result_letter(2, 2) == "T"


def _match(order, discipline="singles", my=0, opp=0, nonplaying=False,
           label=None, event=None):
    m = Match(
        date=dt.date(2026, 7, 1),
        category_id=1,
        discipline=discipline,
        my_sets=my,
        opp_sets=opp,
        is_nonplaying=nonplaying,
        nonplaying_label=label,
        order_index=order,
    )
    if event is not None:
        m.event = event
    return m


def test_format_match_cell_grouping_and_prefixes():
    """W scores group into one W(...) entry; doubles get the 'D: ' prefix;
    non-playing labels and event names each get their own line, first."""
    matches = [
        _match(0, my=3, opp=0, event=Event(name="BBTV Open")),
        _match(1, my=3, opp=1),
        _match(2, discipline="doubles", my=1, opp=3),
        _match(3, nonplaying=True, label="Travel"),
    ]
    cell = service.format_match_cell(matches)
    assert cell.split("\n") == [
        "Travel",
        "BBTV Open",
        "W(3-0,3-1)",
        "D: L(1-3)",
    ]


def test_format_match_cell_one_v_two_prefixes():
    """The 1v2 / 2v1 formats get their own cell prefixes, after doubles."""
    cell = service.format_match_cell([
        _match(0, discipline="two_v_one", my=0, opp=3),
        _match(1, discipline="one_v_two", my=3, opp=1),
        _match(2, discipline="doubles", my=3, opp=2),
    ])
    assert cell.split("\n") == ["D: W(3-2)", "1v2: W(3-1)", "2v1: L(0-3)"]


def test_format_match_cell_empty_and_loss_group():
    assert service.format_match_cell([]) == ""
    cell = service.format_match_cell(
        [_match(0, my=1, opp=3), _match(1, my=3, opp=2)]
    )
    # Fixed group order: singles W before singles L, regardless of entry order.
    assert cell.split("\n") == ["W(3-2)", "L(1-3)"]


def test_physical_is_yellow_threshold():
    """Yellow at >= 70% of the 6 checklist items: 4/6 is not enough, 5/6 is."""
    keys = [k for k, _ in service.PHYSICAL_ITEMS]
    assert service.physical_is_yellow([]) is False
    assert service.physical_is_yellow(keys[:4]) is False  # 66.7% < 70%
    assert service.physical_is_yellow(keys[:5]) is True   # 83.3% >= 70%
    assert service.physical_is_yellow(keys) is True
