"""ORM models for tournaments and their registered disciplines."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class Tournament(Base):
    """One upcoming (or past) competition the player takes part in."""

    __tablename__ = "tournament"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    # None = single-day tournament (ends on start_date).
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # Which ranks may enter, free text — formats vary per organizer:
    # "E F G", "F G H I", "tổng 3 người ≥ 21 chấm"…
    level_limit: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    entries: Mapped[list["TournamentEntry"]] = relationship(
        back_populates="tournament",
        cascade="all, delete-orphan",
        order_by="TournamentEntry.id",
    )


class TournamentEntry(Base):
    """One registered discipline within a tournament (a tournament can have
    several: e.g. singles hạng E + doubles hạng D)."""

    __tablename__ = "tournament_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournament.id"), nullable=False, index=True
    )
    discipline: Mapped[str] = mapped_column(String, nullable=False)  # singles|doubles|team
    # Doubles: the partner from the shared player pool.
    partner_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracker_player.id"), nullable=True
    )
    # Team events: optional free text (team name / note); the roster itself
    # is TournamentEntryMember rows referencing the shared player pool.
    team_members: Mapped[str | None] = mapped_column(String, nullable=True)
    division: Mapped[str | None] = mapped_column(String, nullable=True)  # "hạng E", "U40"…

    tournament: Mapped[Tournament] = relationship(back_populates="entries")
    members: Mapped[list["TournamentEntryMember"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="TournamentEntryMember.id",
    )


class TournamentEntryMember(Base):
    """One teammate in a team entry (picked from the shared player pool)."""

    __tablename__ = "tournament_entry_member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("tournament_entry.id"), nullable=False, index=True
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("tracker_player.id"), nullable=False
    )

    entry: Mapped[TournamentEntry] = relationship(back_populates="members")
