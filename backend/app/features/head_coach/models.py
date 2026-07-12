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
