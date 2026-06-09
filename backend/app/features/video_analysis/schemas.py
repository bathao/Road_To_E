"""Pydantic schemas for the Video Analysis API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

ASPECTS = [
    "serve",
    "receive",
    "forehand",
    "backhand",
    "footwork",
    "stance_posture",
    "tactics",
    "mental",
    "physical",
    "other",
]
# Aspects that get a row in the skill ledger ("other" is a catch-all for
# findings, not a skill to rate).
SKILL_ASPECTS = [a for a in ASPECTS if a != "other"]
POLARITIES = ["strength", "weakness", "neutral"]
# Drill focus — steers the analysis prompt. "" / "free" = no steer.
FOCUS_VALUES = ["", "serve_practice", "footwork_drill", "rally", "match", "free"]
FINDING_STATUSES = ["proposed", "accepted", "rejected"]
SKILL_STATUSES = ["strength", "weakness", "improving", "needs_work", "neutral"]


# ----------------------------------------------------------------- profile
class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    handed: str
    grip: str
    style: str
    equipment: str
    physique: str
    serve_summary: str
    footwork_summary: str
    posture_summary: str
    strengths_summary: str
    weaknesses_summary: str
    overall_summary: str
    updated_at: dt.datetime


class ProfileIn(BaseModel):
    """Editable basics + summaries. All optional → partial update."""

    name: str | None = None
    handed: str | None = None
    grip: str | None = None
    style: str | None = None
    equipment: str | None = None
    physique: str | None = None
    serve_summary: str | None = None
    footwork_summary: str | None = None
    posture_summary: str | None = None
    strengths_summary: str | None = None
    weaknesses_summary: str | None = None
    overall_summary: str | None = None


# ------------------------------------------------------- traits / findings
class TraitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aspect: str
    polarity: str
    text: str
    ai_text: str | None = None
    confidence: float | None
    t_ref: float | None = None
    evidence: dict | None = None
    status: str = "proposed"
    source_clip_id: int | None
    created_at: dt.datetime


class TraitIn(BaseModel):
    aspect: str = "other"
    polarity: str = "neutral"
    text: str
    confidence: float | None = None


# --------------------------------------------------------- review a clip
class FindingDecisionIn(BaseModel):
    """One reviewed finding: keep it (accept) or drop it (reject), optionally
    with user edits to the text/aspect/polarity."""

    id: int
    accept: bool = True
    text: str | None = None
    aspect: str | None = None
    polarity: str | None = None


class ReviewIn(BaseModel):
    decisions: list[FindingDecisionIn] = []


# ------------------------------------------------------------- skill ledger
class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aspect: str
    rating: int | None
    status: str
    assessment: str
    priority: int | None
    updated_at: dt.datetime


class SkillIn(BaseModel):
    """Manual edit of a skill (all optional → partial update)."""

    rating: int | None = None
    status: str | None = None
    assessment: str | None = None
    priority: int | None = None


# --------------------------------------------------- progress / metric trends
class MetricTrend(BaseModel):
    """A pose/stroke metric compared to the player's own baseline (Phase 3)."""

    name: str
    label: str
    unit: str = ""
    current: float
    baseline: float
    delta: float
    pct: float | None = None
    better: str = "neutral"  # up | down | neutral — which direction is improvement
    trend: str = "flat"      # improved | declined | flat | changed
    samples: int = 0         # how many earlier clips formed the baseline


# --------------------------------------------------- structured player report
class SkillReportItem(BaseModel):
    aspect: str
    rating: int | None
    status: str
    assessment: str
    priority: int | None
    evidence: list[str] = []  # short text of accepted findings backing this skill


class ReportOut(BaseModel):
    """The systematic, machine-readable view of the player a future module reads."""

    name: str
    handed: str
    grip: str
    style: str
    overall_summary: str
    skills: list[SkillReportItem] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    improvement_priorities: list[str] = []
    metric_trends: list[MetricTrend] = []
    clips_reviewed: int = 0
    findings_accepted: int = 0


# ------------------------------------------------------------------- clips
class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clip_id: int
    model: str
    language: str
    summary: str
    raw: dict  # parsed raw_json
    pose: dict  # parsed pose_json
    progress: list[MetricTrend] = []  # this clip's metrics vs the player's baseline
    created_at: dt.datetime


class ClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    clip_type: str
    focus: str = ""
    title: str
    note: str | None
    duration_sec: float | None
    fps: float | None
    frames_sampled: int | None
    width: int | None
    height: int | None
    model: str
    status: str
    error_msg: str | None
    created_at: dt.datetime
    processing_started_at: dt.datetime | None = None
    reviewed_at: dt.datetime | None = None
    me_side: str = ""
    me_appearance: str = ""
    subject_desc: str | None = None
    identified: bool = True


class ClipDetailOut(ClipOut):
    analysis: AnalysisOut | None = None
    traits: list[TraitOut] = []


class ClipCreateIn(BaseModel):
    """Create a clip from a file already on disk (local-only tool). When a trim
    range is given, only the cut segment is kept."""

    local_path: str
    clip_type: str = "training"
    focus: str = ""
    title: str = ""
    note: str | None = None
    model: str | None = None
    trim_start: str | None = None
    trim_end: str | None = None
    me_side: str = ""
    me_appearance: str = ""


class ReanalyzeIn(BaseModel):
    model: str | None = None  # override the VLM model for this run


class IdentifyIn(BaseModel):
    """User-supplied identity for a clip the model couldn't place."""

    me_side: str = ""
    me_appearance: str = ""


# ------------------------------------------------------------ profile images
class ProfileImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_clip_id: int | None
    created_at: dt.datetime


class ProfileImageIn(BaseModel):
    local_path: str


class CropBoxIn(BaseModel):
    """A user-drawn bounding box, normalised to 0..1 of the frame."""

    x: float
    y: float
    w: float
    h: float


# ------------------------------------------------------------------ health
class ModelHealthOut(BaseModel):
    ollama_up: bool
    models: list[str]
    default_model: str
    default_available: bool
    message: str
