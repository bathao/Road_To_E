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
    # Canonical intake slot ('grip', 'style', …). When set, the POST upserts
    # on (player_id, key) — answering an intake question twice edits the row.
    key: str | None = Field(default=None, max_length=40)

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
    key: str | None = None
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


# --------------------------------------------------------------- match log
Side = Literal["me", "opp"]
Place = Literal["R", "M", "L"]
Stance = Literal["right", "center", "left"]
Motion = Literal["pend", "rev", "bh", "toma", "other"]
Spin = Literal["back", "side", "sideback", "top", "none"]
Amount = Literal["light", "med", "heavy"]
Length = Literal["short", "half", "long"]
Stroke = Literal[
    "fhloop", "bhloop", "fhdrive", "bhdrive", "fhpush", "bhpush",
    "flick", "block", "smash", "chop", "other",
]
# Incoming ball the stroke was played against (optional detail).
Ball = Literal["back", "top", "none"]


class ServeIn(BaseModel):
    """One serve of the user's repertoire."""

    name: str = Field(min_length=1, max_length=120)
    stance: Stance | None = None
    motion: Motion | None = None
    spin: Spin
    amount: Amount | None = None
    length: Length
    place: Place | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Serve name cannot be empty.")
        return v


class ServeOut(ServeIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sort_order: int = 0


class ShotIn(BaseModel):
    """One shot of a rally. The first shot of a point is the serve (serve
    attributes), every later one a stroke; `place` is always the landing
    spot on the RECEIVER's side."""

    h: Side
    serve: bool = False
    serve_id: int | None = None  # my repertoire row it was picked from
    stance: Stance | None = None
    motion: Motion | None = None
    spin: Spin | None = None
    amount: Amount | None = None
    length: Length | None = None
    stroke: Stroke | None = None
    ball: Ball | None = None
    # Landing spot on the RECEIVER's side. Optional on a shot that missed
    # (net / out) — the intended direction when the user knows it.
    place: Place | None = None


class PointIn(BaseModel):
    set_no: int = Field(ge=1, le=7)
    server: Side
    shots: list[ShotIn] = Field(min_length=1)
    end_kind: Literal["winner", "error"]
    forced: bool = False
    note: str | None = Field(default=None, max_length=2000)


class PointOut(BaseModel):
    id: int
    match_id: int
    set_no: int
    point_no: int
    server: Side
    winner: Side
    end_kind: str
    forced: bool
    note: str | None = None
    shots: list[ShotIn] = []


class PointNoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class SetIn(BaseModel):
    set_no: int = Field(ge=1, le=7)
    my_points: int | None = Field(default=None, ge=0, le=99)
    opp_points: int | None = Field(default=None, ge=0, le=99)
    first_server: Side | None = None


class SetOut(SetIn):
    model_config = ConfigDict(from_attributes=True)


class SetsIn(BaseModel):
    sets: list[SetIn] = []


class OppServeSeen(BaseModel):
    """A distinct serve this opponent has shown across every charted match
    (the charter offers these as one-tap chips)."""

    stance: Stance | None = None
    motion: Motion | None = None
    spin: Spin | None = None
    amount: Amount | None = None
    length: Length | None = None
    count: int = 0


class MatchLogOut(BaseModel):
    match_id: int
    sets: list[SetOut] = []
    points: list[PointOut] = []
    opp_serves_seen: list[OppServeSeen] = []


class MatchLogStatus(BaseModel):
    match_id: int
    points: int = 0
    sets_typed: int = 0


class ServeStat(BaseModel):
    side: Side
    serve_id: int | None = None
    stance: Stance | None = None
    motion: Motion | None = None
    spin: Spin | None = None
    amount: Amount | None = None
    length: Length | None = None
    place: Place | None = None
    played: int = 0
    won: int = 0  # by the server


class PointNoteOut(BaseModel):
    match_id: int
    date: dt.date | None = None
    set_no: int
    point_no: int
    score: str
    note: str


class StatsOut(BaseModel):
    """Shot statistics over a set of charted points (one match, or every
    charted match against one opponent). Vocabulary codes as keys — the
    frontend labels them."""

    matches: int = 0
    points: int = 0
    points_me: int = 0
    points_opp: int = 0
    # [played, won by me]
    on_my_serve: list[int] = [0, 0]
    on_opp_serve: list[int] = [0, 0]
    # my attacking strokes: stroke → place → [won, lost, missed]
    attacks: dict[str, dict[str, list[int]]] = {}
    # stroke → [unforced, forced]
    errors_me: dict[str, list[int]] = {}
    errors_opp: dict[str, list[int]] = {}
    # stroke → count of clean winners
    winners_me: dict[str, int] = {}
    winners_opp: dict[str, int] = {}
    # the receiver's first shot after a serve: stroke → [point won, lost,
    # missed] — missed = the receive itself went net / out
    receive_me: dict[str, list[int]] = {}
    receive_opp: dict[str, list[int]] = {}
    serves: list[ServeStat] = []
    # "1-2" | "3-4" | "5+" → [me, opp]
    rally_len: dict[str, list[int]] = {}
    # points played from 8-8 on: [me, opp]
    clutch: list[int] = [0, 0]
    notes: list[PointNoteOut] = []
