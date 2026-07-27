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

# Canonical Vietnamese display labels — the single copy shared by this feature
# and the Head Coach (prompt-facing descriptions live in text_synth).
ASPECT_LABEL_VI = {
    "serve": "Giao bóng",
    "receive": "Đỡ giao bóng",
    "forehand": "Phải tay (FH)",
    "backhand": "Trái tay (BH)",
    "footwork": "Bộ chân / di chuyển",
    "stance_posture": "Tư thế",
    "tactics": "Chiến thuật",
    "mental": "Tâm lý",
    "physical": "Thể lực",
}
SETTING_LABEL_VI = {"practice": "Tập", "match": "Đấu"}


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


# (Paste-analysis intake schemas deleted 2026-07-27 with the retired pipeline;
# the stored va_report ROWS stay — build_report still counts reviewed ones.)


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
