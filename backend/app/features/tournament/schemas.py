"""Pydantic schemas for the tournament API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator

DISCIPLINES = ("singles", "doubles", "team")


class EntryIn(BaseModel):
    # Id of the EXISTING entry when editing (None = create new). Daily
    # Tracker matches reference entries by id, so updates must reconcile in
    # place — recreating entries on every PUT orphaned all linked matches
    # (tournament label, rounds, placement bonus — review find 2026-08-09).
    id: int | None = None
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
    # Deepest DECIDED round so far + whether that match was won (None = no
    # decided matches yet). Feeds the MatchEditor's auto-advancing Round
    # default: won a knockout round → next round pre-picked, across days.
    latest_round: str | None = None
    latest_round_won: bool | None = None
    # Knocked out mid-event (user button): no more matches to enter for this
    # entry — the grid highlight / editor tournament mode skip it; every
    # entry marked retires the whole tournament to the Profile record.
    eliminated: bool = False


class EntryEliminatedIn(BaseModel):
    """PATCH body for the knocked-out toggle (false = un-mark a mis-click)."""

    eliminated: bool


class TournamentOut(BaseModel):
    id: int
    name: str
    location: str | None = None
    start_date: dt.date
    end_date: dt.date | None = None
    level_limit: str | None = None
    note: str | None = None
    # Past the LAST day OR results entered for that last day — entering a
    # same-day tournament's results retires it immediately (user 2026-08-01);
    # a multi-day event survives earlier days' results so the strip/coach
    # keep tracking the remaining days (user 2026-08-04). The Daily Tracker
    # moves retired cards to the Profile record. The GUI groups on this
    # flag, not on dates.
    played: bool = False
    entries: list[EntryOut] = []


class TournamentsResponse(BaseModel):
    # Every tournament, upcoming first (soonest start date on top), then past
    # (most recent first). The GUI derives countdown/past locally.
    tournaments: list[TournamentOut] = []


# --------------------------------------------- tournament record (Profile tab)
class RecordMatch(BaseModel):
    """One entered match of a tournament entry, in play order."""

    id: int
    date: dt.date
    round: str | None = None  # group|r64|…|f; None = saved without a round
    discipline: str
    opponent_name: str | None = None
    opponent2_name: str | None = None
    partner_name: str | None = None
    my_sets: int = 0
    opp_sets: int = 0
    won: bool | None = None  # None = no result entered (0-0 / tie)
    elo_delta: float | None = None  # None = not ELO-counted (e.g. pre-anchor)


class RecordEntry(BaseModel):
    """One entry's read-only record: how far it went + the matches behind it.
    Everything is DERIVED from the Daily Tracker matches — nothing stored."""

    entry: EntryOut  # carries the derived final_placement / data_warning
    # Deepest DECIDED round entered (group|r64|…|f); None = no matches yet.
    round_reached: str | None = None
    # Won that deepest match (true + no placement = later rounds missing —
    # entry.data_warning says so).
    reached_won: bool = False
    wins: int = 0
    losses: int = 0
    matches: list[RecordMatch] = []


class RecordTournament(BaseModel):
    id: int
    name: str
    location: str | None = None
    start_date: dt.date
    end_date: dt.date | None = None
    entries: list[RecordEntry] = []


class TournamentRecordResponse(BaseModel):
    # Past tournaments only, newest first — the Profile tab's history view.
    tournaments: list[RecordTournament] = []
