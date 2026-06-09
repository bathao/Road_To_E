"""ORM models for the Video Analysis tab.

The schema revolves around a single player ("me" = Nguyễn Bá Thảo):

- ``VAProfile``  – one living profile row (id=1): basics + AI-maintained summaries.
- ``VAClip``     – one uploaded video clip + processing status.
- ``VAAnalysis`` – the AI result for a clip (one current row per clip).
- ``VATrait``    – atomic strength/weakness *findings* that accumulate across
                   clips; each carries a review ``status`` (proposed→the user
                   confirms accepted/rejected) so only confirmed ones count.
- ``VASkill``    – the systematic skill ledger (one row per aspect): a 1–10
                   rating + status + assessment, synthesised from accepted
                   findings and editable by the user. This is the structured
                   view a future "brain" reads to understand the player.

JSON blobs (``raw_json``, ``pose_json``) are stored as TEXT and (de)serialised
in the service layer to keep this dependency-free on SQLite.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class VAProfile(Base):
    """The player profile (singleton, id=1). Free-text summary fields are a
    'living' profile: editable by the user and refreshable from the traits by
    the LLM."""

    __tablename__ = "va_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, default="Nguyễn Bá Thảo")
    handed: Mapped[str] = mapped_column(String, default="right")  # right | left
    grip: Mapped[str] = mapped_column(String, default="shakehand")  # shakehand | penhold
    style: Mapped[str] = mapped_column(String, default="")  # offensive | all-round | ...
    equipment: Mapped[str] = mapped_column(Text, default="")  # blade + rubbers
    physique: Mapped[str] = mapped_column(Text, default="")  # height / build notes

    # AI/user-maintained synthesis of all clips analysed so far.
    serve_summary: Mapped[str] = mapped_column(Text, default="")
    footwork_summary: Mapped[str] = mapped_column(Text, default="")
    posture_summary: Mapped[str] = mapped_column(Text, default="")
    strengths_summary: Mapped[str] = mapped_column(Text, default="")
    weaknesses_summary: Mapped[str] = mapped_column(Text, default="")
    overall_summary: Mapped[str] = mapped_column(Text, default="")

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class VAClip(Base):
    """An uploaded clip and its processing state."""

    __tablename__ = "va_clip"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String)  # absolute path on disk
    clip_type: Mapped[str] = mapped_column(String, default="training")  # training | match_points
    # Drill focus, steers the analysis prompt: serve_practice|footwork_drill|rally|match|free|""
    focus: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String, default="")
    note: Mapped[str | None] = mapped_column(Text, default=None)

    duration_sec: Mapped[float | None] = mapped_column(Float, default=None)
    fps: Mapped[float | None] = mapped_column(Float, default=None)
    frames_sampled: Mapped[int | None] = mapped_column(Integer, default=None)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)

    model: Mapped[str] = mapped_column(String, default="")
    # pending|processing|awaiting_confirm|needs_id|analyzing|done|error
    status: Mapped[str] = mapped_column(String, default="pending")
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # When the current background job (detect or deep analysis) started — used to
    # show an elapsed timer + estimated progress bar while status is
    # processing/analyzing. Reset each time a new job is kicked off.
    processing_started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Set when the user has reviewed this clip's findings (accepted/rejected).
    # NULL while status=done means "analysed, waiting for the user to confirm".
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # Who in the frame is the user. me_side: where I stand (left|right|top|bottom|
    # alone|""); me_appearance: free text hint ("áo đỏ"); subject_desc: the model's
    # own echo of which player it found; identified: did detection find me;
    # preview_path: a crop of the detected person, shown for the user to confirm.
    me_side: Mapped[str] = mapped_column(String, default="")
    me_appearance: Mapped[str] = mapped_column(String, default="")
    subject_desc: Mapped[str | None] = mapped_column(Text, default=None)
    identified: Mapped[bool] = mapped_column(Boolean, default=True)
    preview_path: Mapped[str | None] = mapped_column(String, default=None)

    analysis: Mapped["VAAnalysis | None"] = relationship(
        "VAAnalysis", back_populates="clip", uselist=False, cascade="all, delete-orphan"
    )
    traits: Mapped[list["VATrait"]] = relationship(
        "VATrait", back_populates="source_clip", cascade="all, delete-orphan"
    )


class VAAnalysis(Base):
    """The current AI analysis for a clip. Re-running replaces this row."""

    __tablename__ = "va_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    clip_id: Mapped[int] = mapped_column(
        ForeignKey("va_clip.id", ondelete="CASCADE"), unique=True, index=True
    )
    model: Mapped[str] = mapped_column(String, default="")
    language: Mapped[str] = mapped_column(String, default="vi")
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")  # full VLM output
    pose_json: Mapped[str] = mapped_column(Text, default="{}")  # aggregated pose metrics
    strokes_json: Mapped[str] = mapped_column(Text, default="[]")  # segmented strokes + phases
    metrics_json: Mapped[str] = mapped_column(Text, default="[]")  # flat {name,value,unit} list
    ball_json: Mapped[str] = mapped_column(Text, default="{}")  # ball/table tracking (NC1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    clip: Mapped[VAClip] = relationship("VAClip", back_populates="analysis")


class VAProfileImage(Base):
    """A reference image of the user, used to auto-identify them in clips. Grows
    automatically from labelled clips (cropped to the user) and from manual adds."""

    __tablename__ = "va_profile_image"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String)  # absolute path under PROFILE_REFS_DIR
    source_clip_id: Mapped[int | None] = mapped_column(
        ForeignKey("va_clip.id", ondelete="SET NULL"), default=None, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VATrait(Base):
    """An atomic finding about the player, accumulated across clips. Findings
    start as ``proposed`` (the AI's suggestion) and only count once the user
    confirms them (``accepted``); rejected ones are kept for provenance."""

    __tablename__ = "va_trait"

    id: Mapped[int] = mapped_column(primary_key=True)
    # serve|receive|forehand|backhand|footwork|stance_posture|tactics|mental|physical|other
    aspect: Mapped[str] = mapped_column(String, index=True, default="other")
    polarity: Mapped[str] = mapped_column(String, index=True, default="neutral")  # strength|weakness|neutral
    text: Mapped[str] = mapped_column(Text)  # current text (may be user-edited)
    ai_text: Mapped[str | None] = mapped_column(Text, default=None)  # original AI text
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    t_ref: Mapped[float | None] = mapped_column(Float, default=None)  # evidence time (sec) in the clip
    # Annotated evidence thumbnail for this finding: JSON {stroke_idx, t, thumb}
    # where ``thumb`` is the filename under VIDEOS_DIR. NULL = no thumbnail.
    evidence_json: Mapped[str | None] = mapped_column(Text, default=None)
    # proposed = AI suggestion awaiting review; accepted = confirmed by the user
    # (counts towards the profile); rejected = dismissed.
    status: Mapped[str] = mapped_column(String, index=True, default="proposed")
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # NULL = manually added by the user; otherwise the clip it was extracted from.
    source_clip_id: Mapped[int | None] = mapped_column(
        ForeignKey("va_clip.id", ondelete="CASCADE"), default=None, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    source_clip: Mapped[VAClip | None] = relationship("VAClip", back_populates="traits")

    @property
    def evidence(self) -> dict | None:
        """Parsed ``evidence_json`` (so Pydantic's from_attributes can read it)."""
        if not self.evidence_json:
            return None
        import json
        try:
            return json.loads(self.evidence_json)
        except (ValueError, TypeError):
            return None


class VASkill(Base):
    """The systematic skill ledger: one row per aspect, holding the player's
    current level. Synthesised from accepted findings by the local text model
    and editable by the user (the user's edit is authoritative)."""

    __tablename__ = "va_skill"

    id: Mapped[int] = mapped_column(primary_key=True)
    aspect: Mapped[str] = mapped_column(String, unique=True, index=True)
    rating: Mapped[int | None] = mapped_column(Integer, default=None)  # 1..10, NULL = unrated
    # strength|weakness|improving|needs_work|neutral
    status: Mapped[str] = mapped_column(String, default="neutral")
    assessment: Mapped[str] = mapped_column(Text, default="")  # qualitative summary
    priority: Mapped[int | None] = mapped_column(Integer, default=None)  # improvement order
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class VAMetric(Base):
    """One numeric pose/stroke metric for a clip — the flat time-series spine the
    future Head Coach reads to track progress over time (e.g. 'knee_flexion_deg_mean',
    'swing_speed_mean', 'tempo_sec'). Re-analysing a clip replaces its rows."""

    __tablename__ = "va_metric"

    id: Mapped[int] = mapped_column(primary_key=True)
    clip_id: Mapped[int] = mapped_column(
        ForeignKey("va_clip.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
