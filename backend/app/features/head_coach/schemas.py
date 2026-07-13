"""Pydantic schemas for the Head Coach API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

# Areas a directive can push on — keeps the strict "tăng cường" orders typed.
DIRECTIVE_AREAS = ["training", "playing_hours", "matches", "skill", "recovery"]

# Weekly metrics a directive can be measured by. When the model tags an order
# with one of these + a numeric target, the app computes the CURRENT WEEK's
# actual from the database and shows live progress (Phase-3 "write-back lite":
# orders become trackable commitments, not injected model-guessed exercises).
DIRECTIVE_METRICS = [
    "physical_sessions_per_week",   # Training Center sessions done
    "racket_hours_per_week",        # racket time (training + ~5 min/set)
    "coach_hours_per_week",         # Train with Coach minutes
    "matches_per_week",             # playing matches (any)
    "singles_matches_per_week",
    "doubles_matches_per_week",
    "matches_vs_pips_per_week",     # matches against a pips opponent
]


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
    # Machine-trackable weekly goal ("" / None when the order isn't per-week
    # quantifiable). See DIRECTIVE_METRICS + GET /directive-progress.
    metric: str = ""
    value: float | None = None


class TacticSuggestion(BaseModel):
    """LEGACY — in-match tactic suggestions were dropped from the verdict
    (2026-07: the coach can't know what tactics the player actually uses).
    Kept so snapshots generated before then still parse."""

    situation: str  # when in a match this applies
    action: str  # what to do


class PlanDay(BaseModel):
    day: str  # e.g. "Thứ 2"
    focus: str  # short label
    detail: str  # what to actually do


# ---------------------------------------------------------------- source bundle
class SourceSummary(BaseModel):
    """A compact, human-readable snapshot of what fed the verdict + freshness.

    Since 2026-07 the coach reads the DATABASE only: tracker volume/results,
    detailed match analytics, physical training, and the player's day notes.
    ``video``/``tactics`` remain solely so snapshots generated before the
    technique-analysis and playbook tabs were retired still parse and render."""

    player: str = ""
    training: dict = {}
    match: dict = {}  # volume + win-rate aggregates for the stats window
    match_detail: dict = {}  # by-level, practice-vs-official, trend, head-to-head
    notes: list[dict] = []  # recent day notes [{date, text}]
    generated_for_range: str = ""  # the date window used for match/training stats
    # Legacy fields (pre-retirement snapshots only).
    video: dict = {}
    tactics: dict = {}


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


# ------------------------------------------------- directive live progress
class DirectiveProgress(BaseModel):
    """Current-week actual vs a directive's weekly target (computed from the
    database, never self-reported)."""

    index: int  # position in the assessment's directives list
    area: str
    order: str
    metric: str
    value: float  # weekly target
    actual: float  # this week's actual (Mon → today)
    pct: int  # 0-100, clamped
    unit_vi: str  # "buổi" | "giờ" | "trận"


class DirectiveProgressOut(BaseModel):
    assessment_id: int | None = None
    week_start: dt.date | None = None
    items: list[DirectiveProgress] = []
