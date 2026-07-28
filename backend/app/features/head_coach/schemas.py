"""Pydantic schemas for the Head Coach API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

# NOTE: the canonical directive area list lives in the prompt (prompt.py) and
# the canonical metric list in service._METRIC_RANGE / _METRIC_UNIT_VI +
# prompt.RESPONSE_SCHEMA's enum — no duplicate constants here.

# ---------------------------------------------------------------- verdict parts
class Priority(BaseModel):
    title: str
    why: str = ""
    source: str = ""  # video | match | training | tactics | overall


class Directive(BaseModel):
    """A concrete order to step things up, with a measurable target."""

    area: str  # training | playing_hours | matches | skill | recovery
    order: str  # the instruction, coach voice
    target: str = ""  # measurable goal, e.g. "≥4 buổi/tuần", "+2 trận đơn/tuần"
    reason: str = ""  # the data that triggered it
    # Machine-trackable weekly goal ("" / None when the order isn't per-week
    # quantifiable). See GET /directive-progress.
    metric: str = ""
    value: float | None = None


class TacticSuggestion(BaseModel):
    """LEGACY — in-match tactic suggestions were dropped from the verdict
    (2026-07: the coach can't know what tactics the player actually uses).
    Kept so snapshots generated before then still parse."""

    situation: str  # when in a match this applies
    action: str  # what to do


class PlanDay(BaseModel):
    """Defaults on every field: the Ollama structured-output grammar only
    *requires* day+focus, so a stored plan item may lack the others — parsing
    it must not turn GET /assessment into a permanent 500."""

    day: str = ""  # e.g. "Thứ 2"
    focus: str = ""  # short label
    detail: str = ""  # what to actually do


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
    coach_notes: list[dict] = []  # coach notebook entries [{date, text}]
    # Upcoming registered tournaments [{name, start_date, days_left, entries…}].
    tournaments: list[dict] = []
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
    unit_vi: str  # display unit: "sessions" | "hours" | "matches"


class DirectiveProgressOut(BaseModel):
    assessment_id: int | None = None
    week_start: dt.date | None = None
    items: list[DirectiveProgress] = []


# ------------------------------------------------------------- coach chat
class ChatMessageOut(BaseModel):
    id: int
    created_at: dt.datetime | None = None
    role: str  # user | coach
    content: str = ""
    status: str = "done"  # pending → done | error (coach rows)
    error_msg: str | None = None
    model: str = ""


class ChatHistoryOut(BaseModel):
    messages: list[ChatMessageOut] = []
    # True while the newest coach reply is still being generated (poll cue).
    pending: bool = False


class ChatSendIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


# ---------------------------------------------------------- coach notebook
class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class NoteOut(BaseModel):
    id: int
    created_at: dt.datetime | None = None
    text: str
    source: str = "chat"  # chat (auto-written) | user (added by the player)


class NotesOut(BaseModel):
    notes: list[NoteOut] = []


# ------------------------------------------------------------- dev log panel
class OllamaModelPs(BaseModel):
    """One model currently loaded by Ollama (GPU/VRAM occupancy)."""

    name: str = ""
    size_mb: int = 0  # total memory footprint
    size_vram_mb: int = 0  # of which on the GPU
    expires_at: str = ""  # when Ollama will unload it


class DebugOut(BaseModel):
    """Recent backend log lines + live Ollama state, for the collapsed dev
    panel on the Coach tab (diagnosing OOM / fallback / slow generations)."""

    logs: list[str] = []
    ollama_ok: bool = False
    ollama_error: str = ""
    loaded_models: list[OllamaModelPs] = []
