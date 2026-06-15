"""Pydantic schemas for the Technique Analysis API (text intake, date-stamped)."""
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
FINDING_STATUSES = ["proposed", "accepted", "rejected"]
SKILL_STATUSES = ["strength", "weakness", "improving", "needs_work", "neutral"]
# The footage setting: tập luyện/khởi động vs thi đấu trận thật.
SETTINGS = ["practice", "match"]


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
    confidence: float | None = None
    status: str = "proposed"
    source_report_id: int | None = None
    created_at: dt.datetime


class TraitIn(BaseModel):
    aspect: str = "other"
    polarity: str = "neutral"
    text: str
    confidence: float | None = None


# --------------------------------------------------------- review findings
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
    setting: str
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


# --------------------------------------------------------------- reports
class ReportCreateIn(BaseModel):
    """Paste an analysis produced elsewhere, tagged with the date + setting."""

    source_text: str
    analysis_date: dt.date | None = None  # default today; backdatable; not future
    setting: str = "practice"  # practice | match
    title: str = ""
    context: str = ""


class AnalysisReportOut(BaseModel):
    """A pasted-analysis entry (the list/detail item)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_date: dt.date
    setting: str
    title: str
    context: str
    source_text: str
    model: str
    status: str
    error_msg: str | None = None
    reviewed_at: dt.datetime | None = None
    created_at: dt.datetime


class AnalysisReportDetailOut(AnalysisReportOut):
    traits: list[TraitOut] = []


# ----------------------------------------- progress over time (for the Coach)
class SkillPoint(BaseModel):
    analysis_date: dt.date
    rating: int | None = None
    status: str = "neutral"


class SkillHistory(BaseModel):
    aspect: str
    setting: str = "practice"
    points: list[SkillPoint] = []


class FindingPoint(BaseModel):
    analysis_date: dt.date
    aspect: str
    polarity: str
    text: str
    setting: str = "practice"  # practice | match


class AspectSettingStat(BaseModel):
    """How an aspect looks in practice vs in real matches — the gap the player
    cares about (good in training, weaker under match pressure)."""

    aspect: str
    practice_strengths: int = 0
    practice_weaknesses: int = 0
    match_strengths: int = 0
    match_weaknesses: int = 0
    practice_samples: list[str] = []  # a few example findings (practice)
    match_samples: list[str] = []     # a few example findings (match)


# --------------------------------------------------- structured player report
class SkillReportItem(BaseModel):
    aspect: str
    setting: str
    rating: int | None
    status: str
    assessment: str
    priority: int | None
    evidence: list[str] = []  # short text of accepted findings backing this skill


class ReportOut(BaseModel):
    """The systematic, machine-readable view of the player the Head Coach reads."""

    name: str
    handed: str
    grip: str
    style: str
    overall_summary: str
    skills: list[SkillReportItem] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    improvement_priorities: list[str] = []
    # Development over time:
    skill_history: list[SkillHistory] = []        # per-aspect dated ratings
    findings_timeline: list[FindingPoint] = []    # dated accepted findings
    # Practice vs match contrast (per aspect).
    practice_vs_match: list[AspectSettingStat] = []
    reports_reviewed: int = 0
    findings_accepted: int = 0


# ------------------------------------------------------------------ health
class ModelHealthOut(BaseModel):
    ollama_up: bool
    models: list[str]
    default_model: str
    default_available: bool
    message: str
