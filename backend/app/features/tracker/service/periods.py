"""Date ranges and week/month bucketing.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _date_range(date_from: dt.date, date_to: dt.date) -> list[dt.date]:
    n = (date_to - date_from).days
    return [date_from + dt.timedelta(days=i) for i in range(n + 1)]


def _first_of_month(d: dt.date) -> dt.date:
    return d.replace(day=1)


def _next_month(d: dt.date) -> dt.date:
    return dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)


def _last_of_month(d: dt.date) -> dt.date:
    return _next_month(d) - dt.timedelta(days=1)


def _bucket_ranges(date_from: dt.date, date_to: dt.date, unit: str):
    """Yield (key, label, b_from, b_to) sub-ranges that tile [from, to]."""
    if unit == "day":
        for d in _date_range(date_from, date_to):
            yield (d.isoformat(), f"{_WEEKDAYS[d.weekday()]} {d.day}", d, d)
        return
    if unit == "week":
        cur = date_from - dt.timedelta(days=date_from.weekday())  # Monday
        n = 0
        while cur <= date_to:
            n += 1
            w_end = cur + dt.timedelta(days=6)
            b_from = max(cur, date_from)
            b_to = min(w_end, date_to)
            yield (cur.isoformat(), f"Week {n}", b_from, b_to)
            cur = cur + dt.timedelta(days=7)
        return
    # default: month
    cur = _first_of_month(date_from)
    while cur <= date_to:
        m_end = _last_of_month(cur)
        b_from = max(cur, date_from)
        b_to = min(m_end, date_to)
        yield (cur.strftime("%Y-%m"), cur.strftime("%b"), b_from, b_to)
        cur = _next_month(cur)
