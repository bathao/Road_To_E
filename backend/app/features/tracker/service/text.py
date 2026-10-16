"""Text helpers (diacritic folding for name matching).

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import unicodedata


def _fold(s: str) -> str:
    """Diacritic-insensitive key for name matching: NFD-strip the accents,
    lowercase, đ→d — "tuan" finds "Tuấn", "pham" finds "Phạm"."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).replace("đ", "d")
