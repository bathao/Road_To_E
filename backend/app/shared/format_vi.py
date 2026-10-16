"""Vietnamese labels and formatters shared by the coach prompts.

The Head Coach (verdict / recap / chat) and the Tactics prompts render the
same database facts; these are the pieces they both use so the wording of
a handicap or a relative level can never drift between tabs.
"""
from __future__ import annotations

import datetime as dt

# Relative levels are derived from POINTS vs the athlete's dynamic ELO
# (hand-picked labels retired 2026-07-27); "unrated" = no points entered yet.
LEVEL_VI = {
    "below": "dưới cơ",
    "equal": "ngang cơ",
    "above": "trên cơ",
    "unrated": "chưa có điểm",
}

# Handicap direction of a match, from the player's side.
HANDICAP_VI = {
    "even": "đánh đồng",
    "receive": "học trò ĐƯỢC CHẤP",
    "give": "học trò CHẤP đối thủ",
}

WEEKDAY_VI = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")


def dm(iso: str) -> str:
    """"2026-07-21" → "21/07" — compact date for match and ELO lines."""
    return f"{iso[8:10]}/{iso[5:7]}"


def day_label_vi(d: dt.date) -> str:
    """"Thứ 6 15/08" — the exact PlanDay.day label the model must copy."""
    return f"{WEEKDAY_VI[d.weekday()]} {d.day:02d}/{d.month:02d}"


def hdc_vi(handicap: int, pattern: str | None) -> str:
    """Compact handicap tag for one match line. Sign convention follows
    Match.handicap: +N = the player GIVES N/set, -N = receives."""
    if not handicap:
        return "đồng"
    spec = pattern or str(abs(handicap))
    return f"chấp {spec}" if handicap > 0 else f"được chấp {spec}"
