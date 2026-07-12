"""ORM models for the Technique Analysis tab (text intake, date-stamped).

The schema revolves around a single player ("me" = Nguyễn Bá Thảo):

- ``VAProfile``       – one living profile row (id=1): basics + AI-maintained summaries.
- ``VAReport``        – one pasted cloud-analysis text, tagged with the date it
                        pertains to (``analysis_date``) + parsing status.
- ``VATrait``         – atomic strength/weakness *findings* parsed from a report,
                        each with a review ``status`` (proposed→accepted/rejected)
                        so only confirmed ones count. Dated via its source report.
- ``VASkill``         – the systematic skill ledger (one row per aspect): a 1–10
                        rating + status + assessment, synthesised from accepted
                        findings and editable by the user.
- ``VASkillSnapshot`` – a dated point of a skill's rating/status, written each
                        time the ledger is rebuilt → the rating-over-time series
                        the Head Coach reads to track development.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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

    # AI/user-maintained synthesis of all reports analysed so far.
    serve_summary: Mapped[str] = mapped_column(Text, default="")
    footwork_summary: Mapped[str] = mapped_column(Text, default="")
    posture_summary: Mapped[str] = mapped_column(Text, default="")
    strengths_summary: Mapped[str] = mapped_column(Text, default="")
    weaknesses_summary: Mapped[str] = mapped_column(Text, default="")
    overall_summary: Mapped[str] = mapped_column(Text, default="")

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class VAReport(Base):
    """One pasted analysis (produced elsewhere, e.g. a cloud model), tagged with
    the date it pertains to. The text model parses it into proposed findings."""

    __tablename__ = "va_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The date the footage/analysis is FROM (user-entered). Defaults to today,
    # can be backdated (logged late), never in the future. This is the temporal
    # spine: findings + skill snapshots are anchored to it so progress is trackable.
    analysis_date: Mapped[dt.date] = mapped_column(Date, index=True, default=dt.date.today)
    title: Mapped[str] = mapped_column(String, default="")
    # The setting the footage is from — the key distinction the player asked for:
    # technique often holds up in practice/warmup but breaks down in real matches.
    # practice = tập luyện / khởi động; match = thi đấu trận thật.
    setting: Mapped[str] = mapped_column(String, index=True, default="practice")
    # Optional finer steer for the parser (e.g. "trận giải", "tập giao bóng").
    context: Mapped[str] = mapped_column(String, default="")
    source_text: Mapped[str] = mapped_column(Text, default="")  # the pasted analysis
    model: Mapped[str] = mapped_column(String, default="")  # which local model parsed it
    # parsing | awaiting_review | reviewed | error
    status: Mapped[str] = mapped_column(String, default="parsing")
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    traits: Mapped[list["VATrait"]] = relationship(
        "VATrait", back_populates="source_report", cascade="all, delete-orphan"
    )


class VATrait(Base):
    """An atomic finding about the player, parsed from a report.

    Parsed findings are auto-``accepted`` (the pasted analysis was already
    curated by the user before being pasted in); only ``accepted`` findings
    count towards the profile. The user can still edit/remove findings or mark
    them ``rejected`` afterwards (kept for provenance). Dated via the source
    report."""

    __tablename__ = "va_trait"

    id: Mapped[int] = mapped_column(primary_key=True)
    # serve|receive|forehand|backhand|footwork|stance_posture|tactics|mental|physical|other
    aspect: Mapped[str] = mapped_column(String, index=True, default="other")
    polarity: Mapped[str] = mapped_column(String, index=True, default="neutral")  # strength|weakness|neutral
    text: Mapped[str] = mapped_column(Text)  # current text (may be user-edited)
    ai_text: Mapped[str | None] = mapped_column(Text, default=None)  # original parsed text
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    # proposed = AI suggestion awaiting review; accepted = confirmed by the user
    # (counts towards the profile); rejected = dismissed.
    status: Mapped[str] = mapped_column(String, index=True, default="proposed")
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # NULL = manually added by the user; otherwise the report it was parsed from.
    source_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("va_report.id", ondelete="CASCADE"), default=None, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    source_report: Mapped[VAReport | None] = relationship("VAReport", back_populates="traits")


class VASkill(Base):
    """The systematic skill ledger. One row per (aspect, setting): the player's
    level is tracked SEPARATELY for practice and for match, because technique
    that holds up in training often breaks down under match pressure. Synthesised
    from that setting's accepted findings and editable by the user."""

    __tablename__ = "va_skill"
    __table_args__ = (UniqueConstraint("aspect", "setting", name="uq_skill_aspect_setting"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    aspect: Mapped[str] = mapped_column(String, index=True)
    setting: Mapped[str] = mapped_column(String, index=True, default="practice")  # practice|match
    rating: Mapped[int | None] = mapped_column(Integer, default=None)  # 1..10, NULL = unrated
    # strength|weakness|improving|needs_work|neutral
    status: Mapped[str] = mapped_column(String, default="neutral")
    assessment: Mapped[str] = mapped_column(Text, default="")  # qualitative summary
    priority: Mapped[int | None] = mapped_column(Integer, default=None)  # improvement order
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class VASkillSnapshot(Base):
    """A dated point of a skill's rating/status — the rating-over-time series.
    Written when the ledger is rebuilt, upserted per (analysis_date, aspect) so
    there is one point per date per aspect. The Head Coach + UI read these to
    show development (e.g. forehand 4 → 5 → 6 over three sessions)."""

    __tablename__ = "va_skill_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_date: Mapped[dt.date] = mapped_column(Date, index=True)
    aspect: Mapped[str] = mapped_column(String, index=True)
    setting: Mapped[str] = mapped_column(String, index=True, default="practice")  # practice|match
    rating: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[str] = mapped_column(String, default="neutral")
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("va_report.id", ondelete="SET NULL"), default=None, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
