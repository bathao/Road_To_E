"""Pydantic request/response models for the Tactical Playbook tab."""
from __future__ import annotations

from pydantic import BaseModel


# ---------- My Tactics ----------
class TacticIn(BaseModel):
    phase: str
    title: str
    when_to_use: str | None = None
    how_to: str | None = None
    follow_up: str | None = None
    risk: str | None = None
    opponent_styles: list[str] = []
    tags: list[str] = []
    confidence: int = 0  # 0-5 stars
    is_favorite: bool = False
    source_key: str | None = None  # Library item it was copied from (if any)


class TacticOut(TacticIn):
    id: int
    sort_order: int


# ---------- Library (static reference catalog) ----------
class LibraryItem(BaseModel):
    key: str
    phase: str
    title: str
    when_to_use: str | None = None
    how_to: str | None = None
    follow_up: str | None = None
    risk: str | None = None
    opponent_styles: list[str] = []
    tags: list[str] = []
    source: str | None = None  # coaching source name (None = hand-authored)
    source_url: str | None = None


# ---------- Meta (phases + suggested chip vocab) ----------
class PhaseMeta(BaseModel):
    key: str
    label: str


class PlaybookMeta(BaseModel):
    phases: list[PhaseMeta]
    spin_tags: list[str]
    placement_tags: list[str]
    opponent_styles: list[str]


# ---------- Reorder ----------
class ReorderIn(BaseModel):
    ids: list[int]  # tactic ids in their new display order
