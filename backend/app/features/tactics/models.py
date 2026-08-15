"""ORM models for the Tactics tab (per-opponent game planning).

Facts are the scouting knowledge base: rows about ME (player_id NULL —
strengths/weaknesses the coach must never re-ask across opponents) and rows
about each opponent. Plans are generated snapshots, one row per run (same
status/polling contract as the Head Coach verdict)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class TacticFact(Base):
    """One scouting fact. player_id NULL = about the USER themselves (global
    across opponents); otherwise about that opponent (tracker_player id —
    ALTER-free new table, so a real FK is fine, but we keep it plain like the
    other cross-feature references and never cascade-delete user knowledge)."""

    __tablename__ = "tactic_fact"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    player_id: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    # strength | weakness | style | note
    kind: Mapped[str] = mapped_column(String, default="note")
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, default="user")  # user | interview


class TacticPlan(Base):
    """One generated game plan against one opponent (a snapshot in time)."""

    __tablename__ = "tactic_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    model: Mapped[str] = mapped_column(String, default="")
    # generating → done | error (same polling contract as hc_assessment).
    status: Mapped[str] = mapped_column(String, default="generating")
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)

    # LLM output (Vietnamese).
    headline: Mapped[str] = mapped_column(Text, default="")
    overall: Mapped[str] = mapped_column(Text, default="")
    serve_receive_json: Mapped[str] = mapped_column(Text, default="[]")
    rally_json: Mapped[str] = mapped_column(Text, default="[]")
    avoid_json: Mapped[str] = mapped_column(Text, default="[]")
    mental_json: Mapped[str] = mapped_column(Text, default="[]")
    # What the coach still lacks — feeds the next interview round.
    data_gaps_json: Mapped[str] = mapped_column(Text, default="[]")

    # Frozen input context (transparency, same idea as hc_assessment).
    sources_json: Mapped[str] = mapped_column(Text, default="{}")
