"""Pydantic schemas for the Tactics tab API."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FactKind = Literal["strength", "weakness", "style", "note"]


# ------------------------------------------------------------- opponent picker
class OpponentOut(BaseModel):
    """One person the user has actually PLAYED AGAINST in singles."""

    id: int
    name: str
    points: int | None = None
    plays_pips: bool = False
    matches_vs: int = 0
    wins: int = 0  # decided matches only
    losses: int = 0
    last_vs: dt.date | None = None


# ---------------------------------------------------------------- scouting facts
class FactIn(BaseModel):
    # None = a fact about ME (global across opponents).
    player_id: int | None = None
    kind: FactKind = "note"
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Fact text cannot be empty.")
        return v


class FactUpdate(BaseModel):
    kind: FactKind | None = None
    text: str | None = None


class FactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    player_id: int | None = None
    kind: str
    text: str
    source: str
    created_at: dt.datetime | None = None


class FactsOut(BaseModel):
    """The two scouting lists the tab shows side by side."""

    me: list[FactOut] = []
    opponent: list[FactOut] = []


class OkOut(BaseModel):
    # Deletes return this instead of 204: an empty body reads as `undefined`
    # in the FE api client, which is also useMutate's failure sentinel.
    ok: bool = True


# ------------------------------------------------------------------- interview
class InterviewQuestion(BaseModel):
    subject: Literal["me", "opponent"]
    kind: FactKind = "note"
    question: str


class InterviewOut(BaseModel):
    model: str
    questions: list[InterviewQuestion] = []


class InterviewIn(BaseModel):
    player_id: int


class AnswerIn(BaseModel):
    subject: Literal["me", "opponent"]
    kind: FactKind = "note"
    question: str
    answer: str


class AnswersIn(BaseModel):
    player_id: int
    items: list[AnswerIn] = []


# ------------------------------------------------------------------- game plan
class PlanOut(BaseModel):
    id: int = 0
    created_at: dt.datetime | None = None
    player_id: int = 0
    model: str = ""
    # empty (no plan yet) | generating | done | error
    status: str = "empty"
    error_msg: str | None = None

    headline: str = ""
    overall: str = ""
    serve_receive: list[str] = []
    rally: list[str] = []
    avoid: list[str] = []
    mental: list[str] = []
    # What the coach still lacks — the user can answer these via facts or the
    # next interview round.
    data_gaps: list[str] = []
