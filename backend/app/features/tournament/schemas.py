"""Pydantic schemas for the tournament API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator

DISCIPLINES = ("singles", "doubles", "team")


class EntryIn(BaseModel):
    discipline: str  # singles | doubles | team
    partner_id: int | None = None  # doubles only
    teammate_ids: list[int] = []  # team only (players from the shared pool)
    team_members: str | None = None  # team only (optional team name / note)
    division: str | None = None  # "hạng E", "U40"…

    @field_validator("discipline")
    @classmethod
    def _known_discipline(cls, v: str) -> str:
        if v not in DISCIPLINES:
            raise ValueError(f"discipline must be one of {DISCIPLINES}")
        return v


class TournamentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str | None = None
    start_date: dt.date
    end_date: dt.date | None = None  # None = single-day
    level_limit: str | None = None  # allowed ranks, free text ("E F G"…)
    note: str | None = None
    entries: list[EntryIn] = []


class EntryOut(BaseModel):
    id: int
    discipline: str
    partner_id: int | None = None
    partner_name: str | None = None  # resolved for display
    teammate_ids: list[int] = []
    teammate_names: list[str] = []  # resolved for display, same order as ids
    team_members: str | None = None
    division: str | None = None
    # DERIVED from the entered matches' rounds (never stored/input): the
    # final result reached so far + the ELO bonus it earned.
    final_placement: str | None = None
    bonus_points: int | None = None
    # Data-gap warning: deepest entered knockout round was WON but the next
    # round is missing → the user forgot to enter matches.
    data_warning: str | None = None


class TournamentOut(BaseModel):
    id: int
    name: str
    location: str | None = None
    start_date: dt.date
    end_date: dt.date | None = None
    level_limit: str | None = None
    note: str | None = None
    entries: list[EntryOut] = []


class TournamentsResponse(BaseModel):
    # Every tournament, upcoming first (soonest start date on top), then past
    # (most recent first). The GUI derives countdown/past locally.
    tournaments: list[TournamentOut] = []
