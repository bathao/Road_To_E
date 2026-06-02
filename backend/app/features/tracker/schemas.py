"""Pydantic request/response models for the tracker tab."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    label: str
    type: str
    color_group: str
    sort_order: int


# ---------- Activity (duration rows) ----------
class ActivityIn(BaseModel):
    date: dt.date
    category_id: int
    duration_minutes: int
    note: str | None = None


class ActivityOut(ActivityIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Match ----------
class MatchIn(BaseModel):
    date: dt.date
    category_id: int
    discipline: str = "singles"  # singles | doubles
    best_of: int = 5  # 3 | 5 | 7
    my_sets: int = 0
    opp_sets: int = 0
    event_name: str | None = None  # resolved to / created as an Event
    is_nonplaying: bool = False
    nonplaying_label: str | None = None  # Travel | Rest
    note: str | None = None
    order_index: int = 0


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: dt.date
    category_id: int
    discipline: str
    best_of: int
    my_sets: int
    opp_sets: int
    event_id: int | None
    event_name: str | None
    is_nonplaying: bool
    nonplaying_label: str | None
    note: str | None
    order_index: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ---------- Physical Training checklist ----------
class PhysicalItemOut(BaseModel):
    key: str
    label: str


class PhysicalChecksIn(BaseModel):
    date: dt.date
    items: list[str]  # the full set of ticked item keys for that day


# ---------- Day note ----------
class DayNoteIn(BaseModel):
    date: dt.date
    text: str


# ---------- Week aggregate ----------
class CellData(BaseModel):
    """Pre-rendered display for one (category, date) cell."""
    display: str = ""
    color: str | None = None  # for the Overall row


# ---------- Stats / Analysis ----------
class MatchStats(BaseModel):
    total: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    sets_won: int = 0
    sets_lost: int = 0
    win_rate: float | None = None  # wins / (wins + losses), 0..1; None if no decided matches


class CategoryMinutes(BaseModel):
    key: str
    label: str
    minutes: int


class BreakdownBucket(BaseModel):
    key: str
    label: str
    date_from: dt.date
    date_to: dt.date
    minutes: int
    days_trained: int
    days_physical: int
    matches: int
    wins: int
    losses: int
    win_rate: float | None


class BreakdownResponse(BaseModel):
    unit: str  # month | week | day
    buckets: list[BreakdownBucket]


class StatsResponse(BaseModel):
    date_from: dt.date
    date_to: dt.date
    num_days: int
    days_trained: int
    days_physical: int
    minutes_total: int
    minutes_by_category: list[CategoryMinutes]
    overall: MatchStats
    singles: MatchStats
    doubles: MatchStats


class WeekResponse(BaseModel):
    start: dt.date
    days: list[dt.date]
    categories: list[CategoryOut]
    activities: list[ActivityOut]
    matches: list[MatchOut]
    cells: dict[str, CellData]  # key = f"{category_id}|{date.isoformat()}"
    physical_checks: dict[str, list[str]]  # iso date -> ticked item keys
    day_notes: dict[str, str]  # iso date -> note text
