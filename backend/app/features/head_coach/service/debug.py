"""The dev log panel payload.

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

from app.features.head_coach import schemas
from app.shared.ollama import (
    loaded_models,
)


# --------------------------------------------------------------- dev log panel
def debug_info() -> schemas.DebugOut:
    """Recent backend log lines + which models Ollama currently holds in
    VRAM — enough to diagnose OOM (something else hogging the GPU), model
    fallback, retries and slow generations from the browser."""
    from app.core import logbuffer  # local import: keeps tests decoupled

    out = schemas.DebugOut(logs=logbuffer.tail())
    try:
        models = loaded_models()
        out.ollama_ok = True
        for m in models:
            out.loaded_models.append(
                schemas.OllamaModelPs(
                    name=m.get("name", ""),
                    size_mb=int(m.get("size", 0) / 1_048_576),
                    size_vram_mb=int(m.get("size_vram", 0) / 1_048_576),
                    expires_at=str(m.get("expires_at", "")),
                )
            )
    except Exception as exc:  # noqa: BLE001 — the panel must render regardless
        out.ollama_error = str(exc)[:300]
    return out
