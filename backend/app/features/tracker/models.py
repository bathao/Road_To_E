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
    """A duration-type entry for a given day and category."""

    __tablename__ = "tracker_activity"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("tracker_category.id"), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String, default=None)


class Event(Base):
    """A named competition/event used for autocomplete (e.g. 'BBTV Open')."""

    __tablename__ = "tracker_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)


class Match(Base):
    """A single match. W/L is derived from my_sets vs opp_sets."""

    __tablename__ = "tracker_match"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("tracker_category.id"), index=True)
    discipline: Mapped[str] = mapped_column(String, default="singles")  # singles | doubles
    best_of: Mapped[int] = mapped_column(Integer, default=5)  # 3 | 5 | 7
    my_sets: Mapped[int] = mapped_column(Integer, default=0)
    opp_sets: Mapped[int] = mapped_column(Integer, default=0)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("tracker_event.id"), default=None)
    is_nonplaying: Mapped[bool] = mapped_column(Boolean, default=False)
    nonplaying_label: Mapped[str | None] = mapped_column(String, default=None)  # Travel | Rest
    note: Mapped[str | None] = mapped_column(String, default=None)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    event: Mapped[Event | None] = relationship("Event", lazy="joined")


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
