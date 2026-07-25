"""Pydantic request/response models for the tracker tab."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    duration_minutes: int = Field(ge=0, le=24 * 60)  # one calendar day max
    note: str | None = None
    is_package_start: bool = False  # first session of a coaching package


class ActivityOut(BaseModel):
    """Output side is deliberately unconstrained: one legacy out-of-range row
    must not 500 every /weeks response that contains it."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    date: dt.date
    category_id: int
    duration_minutes: int
    note: str | None = None
    is_package_start: bool = False


# ---------- Coach packages (10-session blocks) ----------
class CoachPackage(BaseModel):
    number: int
    start_date: dt.date
    end_date: dt.date
    used: int
    size: int
    remaining: int
    over: int
    is_current: bool
    status: str  # ok | low | done | over


class CoachPackagesResponse(BaseModel):
    size: int
    packages: list[CoachPackage]


class CoachStartAllowedResponse(BaseModel):
    allowed: bool


# ---------- Player (opponent / partner pool) ----------
class PlayerIn(BaseModel):
    name: str
    level: Literal["below", "equal", "above"] = "equal"
    note: str | None = None
    plays_pips: bool = False  # opponent uses pimpled rubber ("đánh gai")

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tên người chơi không được để trống.")
        return v


class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    level: str
    note: str | None = None
    plays_pips: bool = False


# ---------- Match ----------
class MatchIn(BaseModel):
    date: dt.date
    category_id: int
    discipline: Literal["singles", "doubles"] = "singles"
    best_of: Literal[3, 5, 7] = 5
    my_sets: int = Field(default=0, ge=0, le=4)  # ≤4 set wins even in a BO7
    opp_sets: int = Field(default=0, ge=0, le=4)
    event_name: str | None = None  # resolved to / created as an Event
    is_nonplaying: bool = False
    nonplaying_label: str | None = None  # Travel | Rest
    note: str | None = None
    # None = "append after the cell's existing matches" (an explicit 0 means
    # "insert first" and must not be treated as unset).
    order_index: int | None = None
    # Who played (player ids). Handicap signed: +N = I give N, -N = I receive.
    opponent_id: int | None = None
    opponent2_id: int | None = None
    partner_id: int | None = None
    handicap: int = 0
    # Per-set sequence for non-uniform ratios ("2-0-2"); None = uniform.
    handicap_pattern: str | None = None


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
    opponent_id: int | None = None
    opponent_name: str | None = None
    opponent_level: str | None = None
    opponent_plays_pips: bool = False
    opponent2_id: int | None = None
    opponent2_name: str | None = None
    opponent2_level: str | None = None
    opponent2_plays_pips: bool = False
    partner_id: int | None = None
    partner_name: str | None = None
    partner_level: str | None = None
    handicap: int = 0
    handicap_pattern: str | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class LastDateResponse(BaseModel):
    date: dt.date | None  # most recent day with any data; None if empty


class LastHandicapResponse(BaseModel):
    """The most recent singles handicap vs one opponent (GUI pre-fill)."""

    found: bool = False
    handicap: int = 0  # signed, as stored
    handicap_pattern: str | None = None


# ---------- Physical Training checklist ----------
class PhysicalItemOut(BaseModel):
    key: str
    label: str


class PhysicalChecksIn(BaseModel):
    date: dt.date
    items: list[str]  # the full set of ticked item keys for that day


class PhysicalChecksOut(BaseModel):
    date: dt.date
    items: list[str]  # the ticked items actually stored (unknown keys dropped)


# ---------- Day note ----------
class DayNoteIn(BaseModel):
    date: dt.date
    text: str


class DayNoteOut(BaseModel):
    date: dt.date
    text: str  # the stored note; empty string when cleared


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
    # Racket time = coach + partner training + match play (sets × ~5 min).
    racket_minutes_total: int = 0
    racket_minutes_training: int = 0
    racket_minutes_matches: int = 0
    overall: MatchStats
    singles: MatchStats
    doubles: MatchStats
    vs_pips: MatchStats  # matches vs an opponent who plays pimpled rubber ("gai")


# ---------- Match Stats tab (named-opponent matches only) ----------
class LevelRecord(BaseModel):
    level: str  # below | equal | above
    stats: MatchStats


class MatchLine(BaseModel):
    """One played match against an opponent (for the head-to-head detail)."""
    date: dt.date
    discipline: str  # singles | doubles
    my_sets: int
    opp_sets: int
    result: str  # W | L | T
    handicap: int = 0
    handicap_pattern: str | None = None
    event_name: str | None = None


class OpponentRecord(BaseModel):
    opponent_id: int
    name: str
    level: str
    played: int
    wins: int
    losses: int
    ties: int
    sets_won: int
    sets_lost: int
    win_rate: float | None
    last_date: dt.date | None
    last_result: str | None  # W | L | T
    matches: list[MatchLine] = []


class OpponentBrief(BaseModel):
    """Lightweight entry for the opponent dropdown."""
    id: int
    name: str
    level: str
    played: int


class DoublesRecord(BaseModel):
    key: str  # stable id for the matchup (partner + opponent pair)
    partner_id: int | None
    partner_name: str | None
    partner_level: str | None
    opp1_id: int
    opp1_name: str
    opp1_level: str
    opp2_id: int | None
    opp2_name: str | None
    opp2_level: str | None
    played: int
    wins: int
    losses: int
    ties: int
    sets_won: int
    sets_lost: int
    win_rate: float | None
    last_date: dt.date | None
    last_result: str | None  # W | L | T
    matches: list[MatchLine] = []


class MatchTrendBucket(BaseModel):
    key: str
    label: str
    date_from: dt.date
    date_to: dt.date
    matches: int
    wins: int
    losses: int
    win_rate: float | None


class MatchStatsResponse(BaseModel):
    date_from: dt.date
    date_to: dt.date
    discipline: str  # all | singles | doubles
    category: str  # all | practice | official
    unit: str  # month | week | day
    overall: MatchStats
    by_level: list[LevelRecord]
    opponents: list[OpponentBrief]  # for the head-to-head dropdown
    singles_h2h: list[OpponentRecord]
    doubles_h2h: list[DoublesRecord]
    trend: list[MatchTrendBucket]


class WeekResponse(BaseModel):
    start: dt.date
    days: list[dt.date]
    categories: list[CategoryOut]
    activities: list[ActivityOut]
    matches: list[MatchOut]
    cells: dict[str, CellData]  # key = f"{category_id}|{date.isoformat()}"
    physical_checks: dict[str, list[str]]  # iso date -> ticked item keys (legacy)
    day_notes: dict[str, str]  # iso date -> note text
    # From this date forward the Physical row mirrors Training Center (read-only
    # in the grid); before it, the legacy checklist stays editable. None = unset.
    physical_cutover: dt.date | None = None
