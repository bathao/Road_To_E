"""ORM models for the Daily Tracker tab."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class Category(Base):
    """A grid row definition (e.g. 'Train with Coach', 'Practice Match', 'Overall')."""

    __tablename__ = "tracker_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    label: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # duration | match | checklist | rating
    color_group: Mapped[str] = mapped_column(String, default="none")  # green | yellow | none
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Activity(Base):
    """A duration-type entry for a given day and category.

    (date, category_id) is unique — the PUT /activities upsert relies on it.
    On existing DBs the index is added by seed.migrate (skipped with a warning
    if legacy duplicates exist; no data is ever deleted)."""

    __tablename__ = "tracker_activity"
    __table_args__ = (
        UniqueConstraint("date", "category_id", name="uq_tracker_activity_date_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("tracker_category.id"), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String, default=None)
    # Marks the first session of a new coaching package (10-session block).
    # Only meaningful for the 'train_with_coach' category.
    is_package_start: Mapped[bool] = mapped_column(Boolean, default=False)


class Event(Base):
    """A named competition/event used for autocomplete (e.g. 'BBTV Open')."""

    __tablename__ = "tracker_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)


class Player(Base):
    """A person the user plays — opponent or doubles partner (one shared pool).

    ``level`` is relative to the user (below | equal | above) and lives on the
    profile (editable), not snapshotted per match.
    """

    __tablename__ = "tracker_player"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    level: Mapped[str] = mapped_column(String, default="equal")  # below | equal | above
    note: Mapped[str | None] = mapped_column(String, default=None)
    # Whether this opponent uses pimpled rubber ("đánh gai"). A property of the
    # person (by name), not of an individual match — all existing players default
    # to False; flip it once and every match against them counts as "vs pips".
    plays_pips: Mapped[bool] = mapped_column(Boolean, default=False)
    # BBTV Open points (G = 800–1000, F ≤1200, E ≤1400, …), maintained BY HAND
    # in the Database tab. Static anchors: only the user's own rating is
    # dynamic (ELO); NULL = not rated yet. Supersedes `level` eventually.
    points: Mapped[int | None] = mapped_column(Integer, default=None)


class Setting(Base):
    """Tiny key-value store for app-level knobs (e.g. the user's own points)."""

    __tablename__ = "tracker_setting"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


class Match(Base):
    """A single match. W/L is derived from my_sets vs opp_sets."""

    __tablename__ = "tracker_match"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("tracker_category.id"), index=True)
    discipline: Mapped[str] = mapped_column(String, default="singles")  # singles | doubles
    # 3 | 5 | 7. Basic bounds are enforced in schemas.MatchIn (Literal/ge/le);
    # full score-vs-best_of consistency stays client-side (frontend scores.ts).
    best_of: Mapped[int] = mapped_column(Integer, default=5)
    my_sets: Mapped[int] = mapped_column(Integer, default=0)
    opp_sets: Mapped[int] = mapped_column(Integer, default=0)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("tracker_event.id"), default=None)
    is_nonplaying: Mapped[bool] = mapped_column(Boolean, default=False)
    nonplaying_label: Mapped[str | None] = mapped_column(String, default=None)  # Travel | Rest
    note: Mapped[str | None] = mapped_column(String, default=None)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Who played. Singles: opponent_id. Doubles: partner_id + opponent_id (#1) +
    # opponent2_id (#2). Handicap is signed: +N = I give N points, -N = I receive.
    opponent_id: Mapped[int | None] = mapped_column(ForeignKey("tracker_player.id"), default=None)
    opponent2_id: Mapped[int | None] = mapped_column(ForeignKey("tracker_player.id"), default=None)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("tracker_player.id"), default=None)
    handicap: Mapped[int] = mapped_column(Integer, default=0)
    # Per-set handicap sequence for non-uniform ratios ("2-0-2" = set 1: 2,
    # set 2: 0, set 3: 2). None = uniform (`handicap` alone carries it). When
    # set, `handicap` stores the signed per-set AVERAGE (rounded, min 1) so
    # sign-based analytics keep working unchanged.
    handicap_pattern: Mapped[str | None] = mapped_column(String, default=None)

    # Points of the involved players AT MATCH TIME (user decision 2026-07-26:
    # raising a player's static points later must NOT rewrite old matches —
    # the new value only applies from the raise onward). Snapshotted on create
    # and re-snapshotted only for a slot whose PLAYER changes on update.
    # NULL = no snapshot (legacy/backfilled row) → the ELO replay falls back
    # to the player's current points.
    opp_points_snap: Mapped[int | None] = mapped_column(Integer, default=None)
    opp2_points_snap: Mapped[int | None] = mapped_column(Integer, default=None)
    partner_points_snap: Mapped[int | None] = mapped_column(Integer, default=None)

    # Default (lazy="select") loading. The bulk readers eager-load these with
    # selectinload() in service._load_range / build_match_stats to avoid N+1;
    # single-match CRUD paths just lazy-load on access while the session is open.
    event: Mapped[Event | None] = relationship("Event")
    opponent: Mapped[Player | None] = relationship("Player", foreign_keys=[opponent_id])
    opponent2: Mapped[Player | None] = relationship("Player", foreign_keys=[opponent2_id])
    partner: Mapped[Player | None] = relationship("Player", foreign_keys=[partner_id])


class PhysicalCheck(Base):
    """One ticked exercise for the Physical Training checklist on a given day."""

    __tablename__ = "tracker_physical_check"
    __table_args__ = (
        UniqueConstraint("date", "item_key", name="uq_tracker_physical_check"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    item_key: Mapped[str] = mapped_column(String, index=True)


class DayNote(Base):
    """A free-text note for a day (things to pay attention to)."""

    __tablename__ = "tracker_day_note"
    __table_args__ = (UniqueConstraint("date", name="uq_tracker_day_note_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    text: Mapped[str] = mapped_column(String)
