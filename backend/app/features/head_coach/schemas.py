"""Pydantic schemas for the Head Coach API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

# Areas a directive can push on — keeps the strict "tăng cường" orders typed.
DIRECTIVE_AREAS = ["training", "playing_hours", "matches", "skill", "tactics", "recovery"]


# ---------------------------------------------------------------- verdict parts
class Priority(BaseModel):
    title: str
    why: str = ""
    source: str = ""  # video | match | training | tactics | overall


class Directive(BaseModel):
    """A concrete order to step things up, with a measurable target."""

    area: str  # one of DIRECTIVE_AREAS
    order: str  # the instruction, coach voice
    target: str = ""  # measurable goal, e.g. "≥4 buổi/tuần", "+2 trận đơn/tuần"
    reason: str = ""  # the data that triggered it


class TacticSuggestion(BaseModel):
    situation: str  # when in a match this applies
    action: str  # what to do


class PlanDay(BaseModel):
    day: str  # e.g. "Thứ 2"
    focus: str  # short label
    detail: str  # what to actually do


# ---------------------------------------------------------------- source bundle
class SourceSummary(BaseModel):
    """A compact, human-readable snapshot of what fed the verdict + freshness."""

    video: dict = {}
    training: dict = {}
    match: dict = {}
    tactics: dict = {}
    generated_for_range: str = ""  # the date window used for match/training stats


# ----------------------------------------------------------------- the verdict
class AssessmentOut(BaseModel):
    id: int | None = None
    created_at: dt.datetime | None = None
    model: str = ""
    status: str = "done"  # generating | done | error
    error_msg: str | None = None
    overall_assessment: str = ""
    top_priorities: list[Priority] = []
    directives: list[Directive] = []
    tactics: list[TacticSuggestion] = []
    week_plan: list[PlanDay] = []
    watch_items: list[str] = []
    sources: SourceSummary = SourceSummary()
    # True when no snapshot exists yet (the tab should prompt the user to generate).
    empty: bool = False


class SourcesOut(BaseModel):
    """The live bundle, for the transparency / debug view (no AI call)."""

    sources: SourceSummary


class GenerateStatusOut(BaseModel):
    """State of the most recent generation attempt (polled by the GUI)."""

    id: int | None = None
    status: str = "none"  # none | generating | done | error
    error_msg: str | None = None
