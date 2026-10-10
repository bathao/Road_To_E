"""ORM models for the Tactics tab (per-opponent game planning).

Facts are the scouting knowledge base: rows about ME (player_id NULL —
strengths/weaknesses the coach must never re-ask across opponents) and rows
about each opponent. Plans are generated snapshots, one row per run (same
status/polling contract as the Head Coach verdict)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, utcnow as _utcnow


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
    source: Mapped[str] = mapped_column(String, default="user")  # user | interview | intake
    # Canonical intake-question slot ('grip', 'style', …). NULL = free-form
    # fact. One row per (player_id, key): the intake form upserts, and the
    # GUI shows an intake question only while its key has no row — that is
    # the "ask once, only fill what's missing" contract (user 2026-08-17).
    key: Mapped[str | None] = mapped_column(String, default=None, index=True)


class TacticReflection(Base):
    """The student's own post-match read on ONE opponent (2026-08-17).
    Deliberately separate from facts: a fact is a settled one-line
    conclusion, a reflection is dated free-form SUBJECTIVE analysis the
    coach must cross-check against the H2H data (and newer reflections
    override older ones). The iterate loop: write a reflection →
    regenerate the plan → answer its data_gaps → repeat."""

    __tablename__ = "tactic_reflection"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)


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


# --------------------------------------------------------------- match log
# Point-by-point charting of a few hand-picked singles matches (2026-10-10):
# the user logs every rally of a match they want analysed in depth, the app
# derives the shot statistics the coach can reason about ("FH loop to the
# right: 6 won / 2 lost / 3 missed") instead of prose. Vocabulary codes are
# English and fixed (frontend vocab.ts carries the Vietnamese chip labels):
#   stance  right | center | left            (server's position, optional)
#   motion  pend | rev | bh | toma | other    (serve motion, optional)
#   spin    back | side | sideback | top | none
#   amount  light | med | heavy               (optional)
#   length  short | half | long
#   place   R | M | L  — ALWAYS from the RECEIVER's side of the table
#   stroke  fhloop | bhloop | fhdrive | bhdrive | fhpush | bhpush | flick |
#           block | smash | chop


class TacticServe(Base):
    """One named serve in the USER's repertoire ("bài giao"), shown as a
    one-tap chip for every opponent. Points copy the serve's attributes at
    log time, so editing or deleting a serve never rewrites history."""

    __tablename__ = "tactic_serve"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    stance: Mapped[str | None] = mapped_column(String, default=None)
    motion: Mapped[str | None] = mapped_column(String, default=None)
    spin: Mapped[str] = mapped_column(String)
    amount: Mapped[str | None] = mapped_column(String, default=None)
    length: Mapped[str] = mapped_column(String)
    # Default landing spot (receiver's side); the charter pre-selects it.
    place: Mapped[str | None] = mapped_column(String, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TacticSet(Base):
    """Set score of one set of one match, typed by hand (sets that have
    points logged derive their score from the points instead)."""

    __tablename__ = "tactic_set"
    __table_args__ = (UniqueConstraint("match_id", "set_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("tracker_match.id", ondelete="CASCADE"), index=True
    )
    set_no: Mapped[int] = mapped_column(Integer)
    my_points: Mapped[int | None] = mapped_column(Integer, default=None)
    opp_points: Mapped[int | None] = mapped_column(Integer, default=None)
    # me | opp — who served first in this set (set 1 is chosen, later sets
    # alternate; stored per set so an odd real-life sequence can be kept).
    first_server: Mapped[str | None] = mapped_column(String, default=None)


class TacticPoint(Base):
    """One rally of a charted match: who served, the shot chain, how it
    ended. `shots_json` = list of {h: me|opp, serve: bool, …attributes,
    place} — the first entry is always the serve."""

    __tablename__ = "tactic_point"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("tracker_match.id", ondelete="CASCADE"), index=True
    )
    set_no: Mapped[int] = mapped_column(Integer)
    point_no: Mapped[int] = mapped_column(Integer)
    server: Mapped[str] = mapped_column(String)  # me | opp
    winner: Mapped[str] = mapped_column(String)  # me | opp (derived, stored)
    end_kind: Mapped[str] = mapped_column(String)  # winner | error
    forced: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    shots_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
