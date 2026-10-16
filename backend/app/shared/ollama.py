"""Local LLM plumbing shared by the Head Coach and Tactics features.

Everything that talks to the Ollama HTTP API lives here: which model to use,
one non-streaming structured-output chat call, the "empty first reply" retry
and the VRAM probe the dev panel shows. Features import these by name and
tests monkeypatch them on the importing module (``hc_service.resolve_model``,
``tactics_service._ollama_chat``), so callers must reference them through
their own module globals, never via ``ollama.<name>`` at call time.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

import httpx

from app.core.settings import HEAD_COACH_MODEL, OLLAMA_BASE_URL, TEXT_MODEL

log = logging.getLogger(__name__)

# Context window handed to every call; the biggest prompt (verdict bundle +
# long chat history) stays well inside it.
NUM_CTX = 16384
# A cold 9B model on a 16GB GPU can take minutes for a long verdict.
CHAT_TIMEOUT_S = 600.0
# Probes (model list, VRAM) must never stall the GUI.
PROBE_TIMEOUT_S = 5.0


def resolve_model() -> str:
    """HEAD_COACH_MODEL when it's actually pulled in Ollama; else fall back to
    the shared TEXT_MODEL (logged). If the probe itself fails, return the
    configured model and let the chat call surface the real error."""
    if HEAD_COACH_MODEL == TEXT_MODEL:
        return HEAD_COACH_MODEL
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=PROBE_TIMEOUT_S)
        resp.raise_for_status()
        names = {m["name"] for m in resp.json().get("models", [])}
    except Exception:  # noqa: BLE001 — probe failure ≠ model missing
        return HEAD_COACH_MODEL
    if HEAD_COACH_MODEL in names or f"{HEAD_COACH_MODEL}:latest" in names:
        return HEAD_COACH_MODEL
    log.warning(
        "head coach model %r is not pulled in Ollama; falling back to %r "
        "(run: ollama pull %s)", HEAD_COACH_MODEL, TEXT_MODEL, HEAD_COACH_MODEL,
    )
    return TEXT_MODEL


def ollama_chat(
    model: str, messages: list[dict], schema: dict, temperature: float, tag: str
) -> dict:
    """One non-streaming structured-output call against the local Ollama chat
    API — the single place that owns the payload shape / timeout / num_ctx.

    Always returns a dict: an empty or non-object reply becomes ``{}`` (the
    callers' "empty reply" checks handle it), and a reply that is not valid
    JSON raises a ValueError whose message the GUI can show instead of a
    raw JSONDecodeError."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": schema,
        "options": {"temperature": temperature, "num_ctx": NUM_CTX},
    }
    t0 = time.monotonic()
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=CHAT_TIMEOUT_S)
    resp.raise_for_status()
    log.info("%s: model=%s took=%.1fs", tag, model, time.monotonic() - t0)
    content = resp.json().get("message", {}).get("content", "")
    if not content:
        return {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        log.warning("%s: model returned invalid JSON: %r", tag, content[:200])
        raise ValueError("Model trả về JSON không hợp lệ — bấm chạy lại.") from exc
    return data if isinstance(data, dict) else {}


def call_with_empty_retry(call: Callable[[], dict], key: str, tag: str, model: str) -> dict:
    """Run a structured-output call; retry ONCE when the payload's `key` field
    comes back blank. The first call right after the model loads can return an
    empty object (seen in smoke tests); once warm it answers fine."""
    data = call()
    if not (data.get(key) or "").strip():
        log.warning("%s: empty %r from %s, retrying once", tag, key, model)
        data = call()
    return data


def loaded_models() -> list[dict]:
    """What Ollama currently holds in VRAM (``/api/ps``) — raw dicts with
    ``name`` / ``size`` / ``size_vram`` / ``expires_at``. Raises on any
    failure; the caller decides how to show it."""
    resp = httpx.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=PROBE_TIMEOUT_S)
    resp.raise_for_status()
    return list(resp.json().get("models", []))
