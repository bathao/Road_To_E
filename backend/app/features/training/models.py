"""ORM models for the Training Center tab.

A Tier-1 specialist coach for off-table physical training. The *programs*
(which exercises make up each session of each level) are static reference
content in ``program.py`` and are never stored here — the DB only holds the
player's progress: which level they are on, which sessions they completed, and
which exercises they ticked.

Key design choice: a session's ``day_index`` is its position in a level's
program (1..N), NOT a calendar date. ``done_on`` records the calendar date a
session was actually completed; that (and only that) is what the Daily Tracker
reads. The two axes never conflict.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class TrainingState(Base):
    """Singleton (id=1) holding the player's overall training progress."""

    __tablename__ = "tc_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_level: Mapped[str] = mapped_column(String, default="foundation")
    # Comma-separated level keys the player has unlocked (always includes the
    # default foundation level).
    unlocked_levels: Mapped[str] = mapped_column(String, default="foundation")
    level_since: Mapped[dt.date | None] = mapped_column(Date, default=None)
    # The day Training Center took over as the physical-training input surface.
    # Days before this keep their legacy tracker_physical_check data untouched;
    # days on/after this derive the physical signal from tc_session (see service).
    cutover_date: Mapped[dt.date | None] = mapped_column(Date, default=None)
    # Autoregulation: ± overload steps derived from recent pain/RPE feedback.
    intensity_bias: Mapped[int] = mapped_column(Integer, default=0)


class TrainingSession(Base):
    """One session = one "Day" tile in a level's program.

    Materialised lazily: a row exists once the tile has been opened. Status
    moves unlocked -> done; we never re-lock a completed session.
    """

    __tablename__ = "tc_session"
    __table_args__ = (
        UniqueConstraint("level", "day_index", name="uq_tc_session_level_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String, index=True)
    day_index: Mapped[int] = mapped_column(Integer)  # 1..N within the level
    day_type: Mapped[str] = mapped_column(String)  # legs | core | balance
    status: Mapped[str] = mapped_column(String, default="unlocked")  # unlocked | done
    done_on: Mapped[dt.date | None] = mapped_column(Date, default=None, index=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, default=None)
    duration_min: Mapped[int | None] = mapped_column(Integer, default=None)
    # Frozen 2026-07-29: only the retired video-prescription injector wrote it.
    adapted: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String, default=None)
    # Post-session feedback (autoregulation + safety): pain none|mild|strong,
    # rpe easy|medium|hard.
    pain: Mapped[str | None] = mapped_column(String, default=None)
    rpe: Mapped[str | None] = mapped_column(String, default=None)

    items: Mapped[list["TrainingSessionItem"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TrainingSessionItem.sort_order",
    )


class TrainingSessionItem(Base):
    """One prescribed exercise within a session, plus whether it was done."""

    __tablename__ = "tc_session_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("tc_session.id", ondelete="CASCADE"), index=True
    )
    exercise_key: Mapped[str] = mapped_column(String)
    # JSON snapshot of the target at prescription time, e.g. {"sets":3,"reps":20}
    # or {"sets":3,"sec":45}. Snapshotted so later program edits don't rewrite
    # what the player was actually told to do.
    target_json: Mapped[str] = mapped_column(String)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    done_at: Mapped[dt.datetime | None] = mapped_column(DateTime, default=None)
    # True for an exercise injected by adaptive prescription (from video
    # analysis), not part of the base program.
    is_prescribed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Why it was prescribed (shown to the user) — set only for prescribed items.
    rx_reason: Mapped[str | None] = mapped_column(String, default=None)
    # User skipped this exercise (e.g. it aggravated the knee) — logged, not done.
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped["TrainingSession"] = relationship(back_populates="items")
