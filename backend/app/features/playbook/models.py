"""ORM models for the Tactical Playbook tab.

Only *My Tactics* live in the database. The Library (general table-tennis
tactics) is static reference content in ``library.py`` and is never stored here.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class Tactic(Base):
    """A single tactic the user can apply (their personal playbook entry).

    Created either by hand or by copying a Library item up into My Tactics.
    Tag-like fields (``opponent_styles``, ``tags``) are stored comma-separated
    and split into lists at the API boundary (see service.py).
    """

    __tablename__ = "playbook_tactic"

    id: Mapped[int] = mapped_column(primary_key=True)
    # serve | receive | third_ball | rally | general
    phase: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    when_to_use: Mapped[str | None] = mapped_column(String, default=None)
    how_to: Mapped[str | None] = mapped_column(String, default=None)
    follow_up: Mapped[str | None] = mapped_column(String, default=None)
    risk: Mapped[str | None] = mapped_column(String, default=None)
    opponent_styles: Mapped[str | None] = mapped_column(String, default=None)
    tags: Mapped[str | None] = mapped_column(String, default=None)
    confidence: Mapped[int] = mapped_column(Integer, default=0)  # 0-5 stars
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # The Library item key this was copied from (None for a hand-entered tactic).
    source_key: Mapped[str | None] = mapped_column(String, default=None, index=True)
