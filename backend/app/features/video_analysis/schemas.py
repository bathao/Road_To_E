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
POLARITIES = ["strength", "weakness", "neutral"]


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


# ------------------------------------------------------------------ traits
class TraitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aspect: str
    polarity: str
    text: str
    confidence: float | None
    source_clip_id: int | None
    created_at: dt.datetime


class TraitIn(BaseModel):
    aspect: str = "other"
    polarity: str = "neutral"
    text: str
    confidence: float | None = None


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
    created_at: dt.datetime


class ClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    clip_type: str
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
