"""ORM models for the Head Coach tab.

Generated output snapshots (verdicts, recaps) + the chat and notebook. The
Head Coach does not collect data — these rows are the synthesised output,
kept so the GUI is stable between page loads. Heavy fields (priorities,
directives, week plan, the raw source bundle) are stored as JSON text; the
schemas layer parses them back out. `tactics_json` is legacy read-only —
kept so pre-2026-07 verdict rows still parse.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class HeadCoachAssessment(Base):
    """One generated holistic verdict + plan (a snapshot in time)."""

    __tablename__ = "hc_assessment"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    model: Mapped[str] = mapped_column(String, default="")  # which AI model produced it
    # generating → done | error. Generation runs on a background task; the GUI
    # polls /status until it leaves `generating`.
    status: Mapped[str] = mapped_column(String, default="done")
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)

    overall_assessment: Mapped[str] = mapped_column(Text, default="")
    # JSON-encoded lists (see schemas.AssessmentOut).
    top_priorities_json: Mapped[str] = mapped_column(Text, default="[]")
    directives_json: Mapped[str] = mapped_column(Text, default="[]")
    tactics_json: Mapped[str] = mapped_column(Text, default="[]")
    week_plan_json: Mapped[str] = mapped_column(Text, default="[]")
    watch_items_json: Mapped[str] = mapped_column(Text, default="[]")

    # A compact snapshot of the inputs the verdict was built from (for the
    # "nguồn dữ liệu" transparency view + a freshness check on later loads).
    sources_json: Mapped[str] = mapped_column(Text, default="{}")


class HeadCoachRecap(Base):
    """One generated recap — the coach's review of a ROLLING window ending
    the day the button was pressed (week = last 7 days, month = last 30 days).

    Generation is button-only (no auto-trigger — user's choice 2026-08-01).
    One row per (period_type, start): pressing again the same day reuses that
    day's row; a new day gets a new row. Only the newest is ever surfaced."""

    __tablename__ = "hc_recap"
    __table_args__ = (UniqueConstraint("period_type", "period_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    model: Mapped[str] = mapped_column(String, default="")
    # generating → done | error (same polling contract as hc_assessment).
    status: Mapped[str] = mapped_column(String, default="generating")
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)

    period_type: Mapped[str] = mapped_column(String)  # week (7d) | month (30d)
    period_start: Mapped[dt.date] = mapped_column(Date, index=True)
    period_end: Mapped[dt.date] = mapped_column(Date)  # the button-press day

    # LLM output (Vietnamese).
    headline: Mapped[str] = mapped_column(Text, default="")
    overall: Mapped[str] = mapped_column(Text, default="")
    went_well_json: Mapped[str] = mapped_column(Text, default="[]")
    concerns_json: Mapped[str] = mapped_column(Text, default="[]")
    focus_next_json: Mapped[str] = mapped_column(Text, default="[]")

    # Code-computed numbers shown above the coach's text (current + previous
    # period) — never touched by the model, stays correct even if the LLM errs.
    stats_json: Mapped[str] = mapped_column(Text, default="{}")
    # The frozen input bundle (transparency, same idea as hc_assessment).
    sources_json: Mapped[str] = mapped_column(Text, default="{}")


class CoachChatMessage(Base):
    """One turn of the player↔coach conversation, kept forever.

    The chat *is* the coach's verbatim memory: every reply is generated with
    the full history read back from this table, so nothing is ever "forgotten"
    or paraphrased away. Coach rows start as ``pending`` (a background task
    fills them in — local LLM, tens of seconds) and become done | error."""

    __tablename__ = "hc_chat_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    role: Mapped[str] = mapped_column(String)  # user | coach
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="done")  # pending → done | error
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)
    model: Mapped[str] = mapped_column(String, default="")  # coach rows: model used


class CoachNote(Base):
    """The coach's notebook: durable facts distilled from the conversation
    (goals, deadlines, constraints, injuries, agreements).

    Auto-written by the model after each chat reply (per the user's explicit
    choice — no confirmation step); the player can also add or delete notes.
    Injected into every chat reply AND every weekly verdict, so both stay
    aligned with what was agreed."""

    __tablename__ = "hc_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="chat")  # chat | user
