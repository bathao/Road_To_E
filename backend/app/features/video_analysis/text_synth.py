"""Local text-model calls for the Technique Analysis tab.

This module holds the (only) AI used by this tab now that video processing is
gone: it runs the **shared local text model** (``settings.TEXT_MODEL`` — the same
one the Head Coach uses) over Ollama to

1. ``extract_findings``    – parse a pasted analysis into structured findings,
2. ``synthesize_profile``  – fold accepted findings into the living profile,
3. ``synthesize_skills``   – turn accepted findings into the skill ledger,
4. ``check_models``        – probe Ollama + report whether the model is pulled.

All output is Vietnamese (content); code stays English. Calls use Ollama's
``format`` (JSON-schema) so the model returns parseable JSON directly.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.settings import OLLAMA_BASE_URL, TEXT_MODEL

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
_ASPECTS = list(_ASPECT_VI.keys())


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
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "{}")
    return json.loads(content) if content else {}


# ---------------------------------------------------------------- 1. parse text
_FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "aspect": {"type": "string", "enum": _ASPECTS},
                    "polarity": {
                        "type": "string",
                        "enum": ["strength", "weakness", "neutral"],
                    },
                    "text": {"type": "string"},
                    "confidence": {"type": "number"},  # 0..1
                },
                "required": ["aspect", "polarity", "text"],
            },
        }
    },
    "required": ["findings"],
}


def extract_findings(
    text: str, basics: dict[str, Any], context: str = ""
) -> list[dict[str, Any]]:
    """Parse a pasted analysis (produced elsewhere) into atomic findings.

    Returns ``[{aspect, polarity, text, confidence}]``. Each finding is ONE
    concrete strength or weakness about a single aspect. ``neutral`` is for notes
    that are neither (e.g. "không quan sát được giao bóng"). The findings are
    proposals — the user reviews them before they count."""
    if not (text or "").strip():
        raise RuntimeError("Chưa có nội dung phân tích để bóc tách.")
    aspect_lines = "\n".join(f"  - {k}: {v}" for k, v in _ASPECT_VI.items())
    ctx = f"\nBối cảnh buổi này: {context}.\n" if context.strip() else "\n"
    user_text = (
        "Đây là một bản phân tích kỹ thuật bóng bàn (do một công cụ khác tạo ra) "
        f"về vận động viên Nguyễn Bá Thảo (thuận tay {basics.get('handed')}, cầm "
        f"vợt {basics.get('grip')}, lối đánh {basics.get('style') or 'chưa rõ'})."
        f"{ctx}"
        "Hãy ĐỌC KỸ và bóc tách thành các NHẬN XÉT riêng lẻ, mỗi nhận xét nói về "
        "MỘT ý cụ thể (một điểm mạnh hoặc một điểm yếu) thuộc một mảng kỹ năng.\n"
        "- aspect: chọn 1 trong các mảng sau:\n"
        f"{aspect_lines}\n"
        "- polarity: strength (điểm mạnh) / weakness (điểm yếu) / neutral (chỉ là "
        "ghi chú trung tính hoặc 'không quan sát được').\n"
        "- text: câu nhận xét súc tích bằng tiếng Việt, giữ nguyên ý của bản gốc, "
        "KHÔNG bịa thêm thông tin không có trong văn bản.\n"
        "- confidence: 0..1, mức chắc chắn của nhận xét.\n\n"
        "=== BẢN PHÂN TÍCH ===\n"
        f"{text.strip()}\n"
        "=== HẾT ===\n"
        "Trả về JSON đúng schema. Nếu văn bản không có nội dung kỹ thuật rõ ràng, "
        "trả về danh sách rỗng."
    )
    data = _chat(
        user_text,
        system="Bạn là trợ lý HLV bóng bàn, bóc tách nhận xét kỹ thuật bằng tiếng Việt.",
        schema=_FINDINGS_SCHEMA,
        temperature=0.1,
        num_ctx=16384,  # the pasted analysis can be long
    )
    items = data.get("findings", []) if isinstance(data, dict) else []
    out: list[dict[str, Any]] = []
    for it in items:
        txt = (it.get("text") or "").strip()
        if not txt:
            continue
        aspect = it.get("aspect")
        out.append({
            "aspect": aspect if aspect in _ASPECTS else "other",
            "polarity": it.get("polarity") if it.get("polarity") in
            ("strength", "weakness", "neutral") else "neutral",
            "text": txt,
            "confidence": it.get("confidence"),
        })
    return out


# ------------------------------------------------------------- 2. profile synth
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
        "Đây là hồ sơ một vận động viên bóng bàn tên Nguyễn Bá Thảo.\n"
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
    )


# --------------------------------------------------------------- 3. skill synth
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
        "Đây là các nhận xét ĐÃ ĐƯỢC XÁC NHẬN về vận động viên bóng bàn Nguyễn Bá "
        f"Thảo (thuận tay {basics.get('handed')}, cầm vợt {basics.get('grip')}, lối "
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
    )
    return data.get("skills", []) if isinstance(data, dict) else []


# ------------------------------------------------------------------- 4. health
def check_models() -> dict[str, Any]:
    """Probe Ollama: is it up, and is the shared text model pulled?"""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return {
            "ollama_up": False,
            "models": [],
            "default_model": TEXT_MODEL,
            "default_available": False,
            "message": "Không kết nối được Ollama. Hãy chắc chắn Ollama đang chạy (ollama serve).",
        }
    available = TEXT_MODEL in models
    msg = "OK" if available else (
        f"Ollama đang chạy nhưng thiếu model '{TEXT_MODEL}'. "
        f"Chạy: ollama pull {TEXT_MODEL}"
    )
    return {
        "ollama_up": True,
        "models": models,
        "default_model": TEXT_MODEL,
        "default_available": available,
        "message": msg,
    }
