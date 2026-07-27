"""Local text-model calls for the player profile engine.

Runs the **shared local text model** (``settings.TEXT_MODEL`` — the same one
the Head Coach uses) over Ollama to

1. ``synthesize_profile``  – fold accepted findings into the living profile,
2. ``synthesize_skills``   – turn accepted findings into the skill ledger.

(The paste-analysis parser ``extract_findings`` and the ``check_models`` probe
were deleted 2026-07-27 with the retired intake pipeline.)

All output is Vietnamese (content); code stays English. Calls use Ollama's
``format`` (JSON-schema) so the model returns parseable JSON directly.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.settings import OLLAMA_BASE_URL, TEXT_MODEL

log = logging.getLogger(__name__)


def _player_name(basics: dict[str, Any]) -> str:
    """The player's (editable) profile name for use inside prompts."""
    return (basics.get("name") or "").strip() or "vận động viên"

_ASPECT_VI = {
    "serve": "giao bóng",
    "receive": "đỡ giao bóng / trả giao",
    "forehand": "phải tay (forehand)",
    "backhand": "trái tay (backhand)",
    "footwork": "bộ chân / di chuyển",
    "stance_posture": "tư thế / thân người",
    "tactics": "chiến thuật",
    "mental": "tâm lý thi đấu",
    "physical": "thể lực",
    "other": "khác",
}
def _chat(user_text: str, system: str, schema: dict, *, temperature: float = 0.2,
          num_ctx: int = 8192, timeout: float = 600.0) -> dict:
    """One structured-output chat call to the shared local text model."""
    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "format": schema,
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    t0 = time.monotonic()
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    log.info(
        "ollama chat: model=%s prompt_chars=%d took=%.1fs",
        TEXT_MODEL, len(user_text), time.monotonic() - t0,
    )
    content = resp.json().get("message", {}).get("content", "{}")
    return json.loads(content) if content else {}


# ------------------------------------------------------------- 1. profile synth
_PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "serve_summary": {"type": "string"},
        "footwork_summary": {"type": "string"},
        "posture_summary": {"type": "string"},
        "strengths_summary": {"type": "string"},
        "weaknesses_summary": {"type": "string"},
        "overall_summary": {"type": "string"},
    },
    "required": [
        "serve_summary", "footwork_summary", "posture_summary",
        "strengths_summary", "weaknesses_summary", "overall_summary",
    ],
}


def synthesize_profile(basics: dict[str, Any], traits: list[dict[str, Any]]) -> dict[str, str]:
    """Fold all accumulated (accepted) traits into the profile summary fields."""
    if not traits:
        raise RuntimeError("Chưa có nhận xét (trait) nào để tổng hợp hồ sơ.")
    bullet = "\n".join(
        f"- [{t['aspect']} / {t['polarity']}] {t['text']}" for t in traits
    )
    user_text = (
        f"Đây là hồ sơ một vận động viên bóng bàn tên {_player_name(basics)}.\n"
        f"Thông tin cơ bản: thuận tay {basics.get('handed')}, cách cầm vợt "
        f"{basics.get('grip')}, lối đánh {basics.get('style') or 'chưa rõ'}.\n\n"
        f"Các nhận xét đã tích lũy từ nhiều buổi:\n{bullet}\n\n"
        "Hãy tổng hợp thành hồ sơ súc tích bằng tiếng Việt, gộp các ý trùng lặp, "
        "nêu xu hướng nổi bật. Trả về JSON đúng schema."
    )
    return _chat(
        user_text,
        system="Bạn là HLV bóng bàn, viết hồ sơ học trò bằng tiếng Việt.",
        schema=_PROFILE_SCHEMA,
        temperature=0.3,
        num_ctx=16384,  # accumulated traits can be long
    )


# --------------------------------------------------------------- 2. skill synth
_SKILLS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "aspect": {"type": "string"},
                    "rating": {"type": "integer"},  # 1..10
                    "status": {
                        "type": "string",
                        "enum": ["strength", "weakness", "improving", "needs_work", "neutral"],
                    },
                    "assessment": {"type": "string"},
                    "priority": {"type": "integer"},  # 1 = highest, 0 = none
                },
                "required": ["aspect", "rating", "status", "assessment", "priority"],
            },
        }
    },
    "required": ["skills"],
}


def synthesize_skills(
    basics: dict[str, Any],
    findings_by_aspect: dict[str, list[dict[str, Any]]],
    setting: str = "practice",
) -> list[dict[str, Any]]:
    """Turn one setting's accepted findings into a skill ledger: a 1–10 rating +
    status + assessment + improvement priority per aspect, scored FOR THAT SETTING
    (practice or match) only. Only aspects with findings are scored. The rating is
    the model's estimate from the written findings — a reference the user can
    override."""
    if not findings_by_aspect:
        raise RuntimeError("Chưa có nhận xét đã duyệt nào để dựng hồ sơ kỹ năng.")
    ctx_vi = "khi THI ĐẤU trận thật" if setting == "match" else "khi TẬP LUYỆN / khởi động"
    blocks = []
    for aspect, items in findings_by_aspect.items():
        vi = _ASPECT_VI.get(aspect, aspect)
        lines = "\n".join(f"  - [{it['polarity']}] {it['text']}" for it in items)
        blocks.append(f"# {aspect} ({vi}):\n{lines}")
    body = "\n\n".join(blocks)
    aspects_list = ", ".join(findings_by_aspect.keys())
    user_text = (
        f"Đây là các nhận xét ĐÃ ĐƯỢC XÁC NHẬN về vận động viên bóng bàn "
        f"{_player_name(basics)} (thuận tay {basics.get('handed')}, cầm vợt {basics.get('grip')}, lối "
        f"đánh {basics.get('style') or 'chưa rõ'}), gom theo từng mảng kỹ năng. "
        f"TẤT CẢ nhận xét dưới đây là {ctx_vi}:\n\n"
        f"{body}\n\n"
        f"Với MỖI mảng có nhận xét ở trên, hãy đánh giá trình độ mảng đó {ctx_vi} "
        "bằng tiếng Việt:\n"
        "- rating: điểm 1–10 (10 = rất tốt, 1 = rất yếu) trong bối cảnh này.\n"
        "- status: strength / weakness / improving / needs_work / neutral.\n"
        "- assessment: 1–2 câu súc tích mô tả trình độ mảng đó trong bối cảnh này.\n"
        "- priority: 1 = ưu tiên cao nhất; 0 = không cần. Mảng càng yếu/quan trọng "
        "thì priority càng nhỏ.\n"
        f"Chỉ chấm các mảng sau: {aspects_list}. Trả về JSON đúng schema."
    )
    data = _chat(
        user_text,
        system="Bạn là HLV bóng bàn, đánh giá trình độ học trò bằng tiếng Việt.",
        schema=_SKILLS_SCHEMA,
        temperature=0.2,
        num_ctx=16384,  # accumulated findings can be long
    )
    return data.get("skills", []) if isinstance(data, dict) else []
