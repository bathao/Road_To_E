"""ORM model for the Head Coach tab.

A single table holding generated verdict snapshots. The Head Coach does not
collect data — these rows are the synthesised output, kept so the verdict is
stable between page loads and so we have a history of how the assessment evolved.
The heavy fields (priorities, directives, tactics, week plan, the raw source
bundle) are stored as JSON text; the schemas layer parses them back out.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String, Text
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
