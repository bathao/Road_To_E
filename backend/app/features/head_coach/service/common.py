"""Shared-layer names under the aliases this package (and its tests) use.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

from app.shared import format_vi
from app.shared.ollama import (
    call_with_empty_retry,
    ollama_chat,
)
from app.shared.time import as_utc

# Shared plumbing under the names this module (and its tests) use. Tests
# monkeypatch ``resolve_model`` / ``_ollama_chat`` on this module, so the
# job code must keep referencing these module globals.
_ollama_chat = ollama_chat


_call_with_empty_retry = call_with_empty_retry


_tz = as_utc


_LEVEL_VI = format_vi.LEVEL_VI


_HANDICAP_VI = format_vi.HANDICAP_VI


_dm = format_vi.dm


_day_label_vi = format_vi.day_label_vi


_hdc_vi = format_vi.hdc_vi
