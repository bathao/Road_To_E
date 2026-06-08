"""The analysis pipeline: sample frames, run MediaPipe pose, call the local VLM.

Kept free of any DB access — callers (the service layer) persist the results.
Heavy libs (cv2, mediapipe) are imported lazily so the web app still boots if
they are missing; pose then degrades gracefully to "unavailable".

VLM inference runs on the GPU via Ollama (separate process); pose runs on CPU.
"""
from __future__ import annotations

import base64
import json
import math
import shutil
import subprocess
from typing import Any

import httpx

from app.core.settings import DEFAULT_TEXT_MODEL, DEFAULT_VLM_MODEL, OLLAMA_BASE_URL

# How many frames to feed each stage. The VLM set is a subset (token/VRAM
# budget); pose can look at more frames since it is cheap on CPU.
VLM_MAX_FRAMES = 14
POSE_MAX_FRAMES = 32
FRAME_MAX_DIM = 768  # downscale longest side before sending to the VLM
# Each frame costs ~1k vision tokens, so 14 frames + prompt + output blows past
# Ollama's 4096 default. Give the VLM a large window; an 8B model + this KV
# cache still fits comfortably in 16GB VRAM.
VLM_NUM_CTX = 32768

# BlazePose (MediaPipe) landmark indices we use.
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
L_WRIST, R_WRIST = 15, 16


# ------------------------------------------------------------------- ffmpeg
def _ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"


def trim_segment(src: str, start_sec: float, end_sec: float, dst: str) -> None:
    """Cut [start, end] out of ``src`` into ``dst`` (re-encoded mp4 for frame
    accuracy). Used to extract a short segment from a long recording before
    analysis.

    Speed: prefer the NVIDIA GPU. We try, in order, (1) full GPU — NVDEC decode +
    NVENC encode with frames kept in GPU memory; (2) NVENC encode with CPU decode
    (if the source codec isn't NVDEC-decodable); (3) pure CPU libx264. Each tier
    falls back to the next on failure, so it works on any machine while using the
    GPU to the max when available. Raises RuntimeError only if all tiers fail."""
    ff = _ffmpeg_bin()
    duration = max(0.0, end_sec - start_sec)
    seek_in = ["-ss", f"{start_sec:.3f}", "-i", src, "-t", f"{duration:.3f}"]
    tail_out = ["-c:a", "aac", "-movflags", "+faststart", dst]

    attempts: list[list[str]] = [
        # (1) Full GPU: decode on NVDEC, keep frames on the GPU, encode on NVENC.
        [ff, "-y", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
         *seek_in, "-c:v", "h264_nvenc", "-preset", "p4", *tail_out],
        # (2) GPU encode only (CPU decode) — for sources NVDEC can't decode.
        [ff, "-y", *seek_in, "-c:v", "h264_nvenc", "-preset", "p4", *tail_out],
        # (3) Pure CPU fallback — always available.
        [ff, "-y", *seek_in, "-c:v", "libx264", "-preset", "veryfast", *tail_out],
    ]

    last_err = ""
    for cmd in attempts:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            return
        last_err = (proc.stderr or "")[-600:]
    raise RuntimeError(f"ffmpeg cắt video thất bại: {last_err}")


# ----------------------------------------------------------------- metadata
def probe(path: str) -> dict[str, Any]:
    """Quick metadata read (fps, duration, size) for the upload step."""
    import cv2

    cap = cv2.VideoCapture(path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    duration = frame_count / fps if fps else None
    return {
        "fps": round(fps, 2) if fps else None,
        "duration_sec": round(duration, 2) if duration else None,
        "frame_count": frame_count or None,
        "width": width or None,
        "height": height or None,
    }


def _even_indices(total: int, want: int) -> list[int]:
    """Evenly-spaced frame indices across [0, total)."""
    if total <= 0:
        return []
    if total <= want:
        return list(range(total))
    step = total / want
    return [min(total - 1, int(i * step)) for i in range(want)]


def _sample_frames(path: str) -> tuple[list, list]:
    """Return (pose_frames_rgb, vlm_frames_rgb). Both are lists of RGB numpy
    arrays; the VLM list is a subset of the pose list."""
    import cv2

    cap = cv2.VideoCapture(path)
    frames_rgb: list = []
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        idxs = _even_indices(total, POSE_MAX_FRAMES) if total else []
        if idxs:
            for idx in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if ok and frame is not None:
                    frames_rgb.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        else:
            # Unknown frame count: read sequentially, keep every Nth.
            grabbed = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                grabbed.append(frame)
            for idx in _even_indices(len(grabbed), POSE_MAX_FRAMES):
                frames_rgb.append(cv2.cvtColor(grabbed[idx], cv2.COLOR_BGR2RGB))
    finally:
        cap.release()

    # VLM subset: evenly pick from the pose frames.
    vlm = [frames_rgb[i] for i in _even_indices(len(frames_rgb), VLM_MAX_FRAMES)]
    return frames_rgb, vlm


def _to_jpeg_b64(frame_rgb) -> str:
    import cv2

    h, w = frame_rgb.shape[:2]
    scale = FRAME_MAX_DIM / max(h, w)
    if scale < 1:
        frame_rgb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)))
    bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("ascii")


# ------------------------------------------------------------- side cropping
# Keep a little overlap past the midline so a player straddling centre isn't cut.
_SIDE_SPAN = 0.55


def crop_side(frame_rgb, side: str):
    """Crop the half of the frame where the user stands (left/right/top/bottom).
    Returns the frame unchanged for unknown/alone/empty sides."""
    h, w = frame_rgb.shape[:2]
    if side == "left":
        return frame_rgb[:, : int(w * _SIDE_SPAN)]
    if side == "right":
        return frame_rgb[:, int(w * (1 - _SIDE_SPAN)) :]
    if side == "top":
        return frame_rgb[: int(h * _SIDE_SPAN), :]
    if side == "bottom":
        return frame_rgb[int(h * (1 - _SIDE_SPAN)) :, :]
    return frame_rgb


# --------------------------------------------------------------------- pose
def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _angle(a, b, c) -> float:
    """Angle ABC in degrees (vertex at b)."""
    v1 = (a.x - b.x, a.y - b.y)
    v2 = (c.x - b.x, c.y - b.y)
    n1 = math.hypot(*v1) or 1e-9
    n2 = math.hypot(*v2) or 1e-9
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    return {
        "mean": round(mean, 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
    }


def run_pose(frames_rgb: list) -> dict[str, Any]:
    """Estimate per-frame body geometry with MediaPipe and aggregate it."""
    try:
        import mediapipe as mp
    except Exception as exc:  # pragma: no cover - install/runtime guard
        return {"available": False, "reason": f"mediapipe unavailable: {exc}"}

    if not frames_rgb:
        return {"available": False, "reason": "no frames"}

    pose = mp.solutions.pose.Pose(
        static_image_mode=True, model_complexity=1, min_detection_confidence=0.5
    )
    stance_ratios: list[float] = []
    knee_angles: list[float] = []
    torso_leans: list[float] = []
    hip_xs: list[float] = []
    hand_elevations: list[float] = []
    detected = 0
    try:
        for frame in frames_rgb:
            res = pose.process(frame)
            lm = getattr(res, "pose_landmarks", None)
            if not lm:
                continue
            pts = lm.landmark

            def vis(i: int) -> bool:
                return pts[i].visibility is None or pts[i].visibility > 0.3

            detected += 1
            shoulder_w = _dist(pts[L_SHOULDER], pts[R_SHOULDER]) or 1e-6

            if vis(L_ANKLE) and vis(R_ANKLE):
                stance_ratios.append(_dist(pts[L_ANKLE], pts[R_ANKLE]) / shoulder_w)

            for hip, knee, ankle in ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE)):
                if vis(hip) and vis(knee) and vis(ankle):
                    knee_angles.append(_angle(pts[hip], pts[knee], pts[ankle]))

            sh_mid = type("P", (), {"x": (pts[L_SHOULDER].x + pts[R_SHOULDER].x) / 2,
                                    "y": (pts[L_SHOULDER].y + pts[R_SHOULDER].y) / 2})
            hip_mid = type("P", (), {"x": (pts[L_HIP].x + pts[R_HIP].x) / 2,
                                     "y": (pts[L_HIP].y + pts[R_HIP].y) / 2})
            # Torso lean from vertical (0° = upright).
            dx, dy = sh_mid.x - hip_mid.x, sh_mid.y - hip_mid.y
            torso_leans.append(abs(math.degrees(math.atan2(dx, -dy))))
            hip_xs.append(hip_mid.x)

            # Highest playing hand relative to shoulder line (>0 = above), norm.
            for wrist in (L_WRIST, R_WRIST):
                if vis(wrist):
                    hand_elevations.append((sh_mid.y - pts[wrist].y) / shoulder_w)
    finally:
        pose.close()

    if detected == 0:
        return {
            "available": True,
            "frames_analyzed": len(frames_rgb),
            "frames_with_pose": 0,
            "reason": "no body detected in sampled frames",
        }

    # Lateral sway = horizontal spread of the hips across the clip (footwork range).
    lateral_sway = round((max(hip_xs) - min(hip_xs)), 3) if hip_xs else None
    return {
        "available": True,
        "frames_analyzed": len(frames_rgb),
        "frames_with_pose": detected,
        "stance_width_ratio": _stats(stance_ratios),
        "knee_flexion_deg": _stats(knee_angles),
        "torso_lean_deg": _stats(torso_leans),
        "lateral_sway": lateral_sway,
        "hand_elevation": _stats(hand_elevations),
    }


def pose_to_text(pose: dict[str, Any]) -> str:
    """Render pose metrics as Vietnamese context for the VLM prompt."""
    if not pose.get("available"):
        return "Không có dữ liệu pose (thiếu thư viện hoặc không phát hiện được người)."
    if not pose.get("frames_with_pose"):
        return "Không phát hiện được cơ thể trong các khung hình được lấy mẫu."

    def fmt(metric: dict | None, unit: str = "") -> str:
        if not metric:
            return "n/a"
        return f"trung bình {metric['mean']}{unit} (từ {metric['min']} đến {metric['max']}{unit})"

    lines = [
        f"- Số khung phát hiện được người: {pose['frames_with_pose']}/{pose['frames_analyzed']}",
        f"- Độ rộng tấn (khoảng cách 2 cổ chân / độ rộng vai): {fmt(pose.get('stance_width_ratio'))} "
        "(>1.4 = tấn rộng, vững; <1.0 = tấn hẹp).",
        f"- Góc gập gối: {fmt(pose.get('knee_flexion_deg'), '°')} (180° = chân thẳng đứng; "
        "càng nhỏ càng khuỵu gối/hạ trọng tâm tốt).",
        f"- Độ nghiêng thân so với phương thẳng đứng: {fmt(pose.get('torso_lean_deg'), '°')}.",
        f"- Biên độ di chuyển ngang của hông (bộ chân): {pose.get('lateral_sway')} "
        "(theo tỉ lệ khung hình; càng lớn = di chuyển chân càng nhiều).",
        f"- Độ cao tay (so với vai, theo độ rộng vai): {fmt(pose.get('hand_elevation'))}.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------- VLM
SYSTEM_PROMPT = (
    "Bạn là một huấn luyện viên bóng bàn chuyên nghiệp, giàu kinh nghiệm phân tích kỹ thuật. "
    "Bạn đang phân tích các khung hình trích từ một clip ngắn của học trò tên 'Nguyễn Bá Thảo'. "
    "Clip có thể có 2 người chơi (Thảo và đối thủ) — NHIỆM VỤ ĐẦU TIÊN là xác định ĐÚNG đâu là "
    "Thảo dựa trên ảnh tham chiếu và/hoặc gợi ý (vị trí, màu áo, tay thuận) rồi CHỈ phân tích "
    "Thảo, bỏ qua đối thủ. Ở trường 'subject' hãy mô tả ngắn người bạn đã chọn (vị trí + ngoại "
    "hình). Nếu KHÔNG chắc chắn đâu là Thảo, đặt identified=false và để các phần phân tích trống. "
    "Khi chắc chắn, phân tích điểm mạnh/yếu về: giao bóng, thuận tay (forehand), trái tay "
    "(backhand), bộ chân (footwork), tư thế/thân người, chiến thuật; dựa cả vào số liệu pose. "
    "Trả lời HOÀN TOÀN bằng tiếng Việt, cụ thể, mang tính huấn luyện. Chỉ trả JSON đúng schema, "
    "không thêm chữ nào ngoài JSON. Mục nào không quan sát rõ thì ghi 'không quan sát rõ', không bịa."
)

# Ollama structured-output JSON schema (constrains the model's response).
_ASPECT_ENUM = [
    "serve", "receive", "forehand", "backhand", "footwork",
    "stance_posture", "tactics", "mental", "physical", "other",
]
_TRAIT_ITEM = {
    "type": "object",
    "properties": {
        "aspect": {"type": "string", "enum": _ASPECT_ENUM},
        "text": {"type": "string"},
    },
    "required": ["aspect", "text"],
}
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "identified": {"type": "boolean"},
        "confidence": {"type": "number"},
        "subject": {"type": "string"},
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": _TRAIT_ITEM},
        "weaknesses": {"type": "array", "items": _TRAIT_ITEM},
        "serve": {
            "type": "object",
            "properties": {"type": {"type": "string"}, "notes": {"type": "string"}},
            "required": ["type", "notes"],
        },
        "footwork": {
            "type": "object",
            "properties": {"notes": {"type": "string"}},
            "required": ["notes"],
        },
        "posture": {
            "type": "object",
            "properties": {"notes": {"type": "string"}},
            "required": ["notes"],
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "identified", "confidence", "subject", "summary", "strengths",
        "weaknesses", "serve", "footwork", "posture", "recommendations",
    ],
}

_SIDE_VI = {
    "left": "bên trái", "right": "bên phải",
    "top": "phía trên (xa camera)", "bottom": "phía dưới (gần camera)",
}

_CLIP_TYPE_VI = {
    "training": "clip tập luyện",
    "match_points": "vài điểm trong một trận đấu",
}


REF_MAX = 4  # reference images sent per analysis (token budget)


def _identity_block(reference_images_b64: list[str], me_side: str,
                    me_appearance: str, handed: str) -> str:
    """The Vietnamese 'who is Thảo' instructions for the prompt."""
    lines: list[str] = []
    if reference_images_b64:
        lines.append(
            f"- {len(reference_images_b64)} ảnh ĐẦU TIÊN là ảnh tham chiếu của Nguyễn Bá Thảo "
            "(từ các clip trước). Hãy tìm đúng người giống các ảnh này trong clip."
        )
    if me_side == "alone":
        lines.append("- Trong clip chỉ có một mình Thảo.")
    elif me_side in _SIDE_VI:
        lines.append(f"- Người dùng cho biết Thảo ở {_SIDE_VI[me_side]} khung hình.")
    if me_appearance:
        lines.append(f"- Ngoại hình của Thảo: {me_appearance}.")
    lines.append(f"- Thảo thuận tay {'trái' if handed == 'left' else 'phải'}.")
    if not reference_images_b64 and me_side not in _SIDE_VI and me_side != "alone" \
            and not me_appearance:
        lines.append("- Chưa có thông tin nhận diện. Nếu không chắc đâu là Thảo, đặt identified=false.")
    return "\n".join(lines)


def call_vlm(images_b64: list[str], pose_text: str, clip_type: str, model: str, *,
             reference_images_b64: list[str] | None = None, me_side: str = "",
             me_appearance: str = "", handed: str = "right") -> dict[str, Any]:
    """Send reference images + frames + pose context to Ollama; return parsed JSON."""
    refs = (reference_images_b64 or [])[:REF_MAX]
    user_text = (
        f"Có {len(refs)} ảnh tham chiếu (nếu >0) rồi đến {len(images_b64)} khung hình trích đều "
        f"từ một {_CLIP_TYPE_VI.get(clip_type, 'clip')} (theo thứ tự thời gian).\n\n"
        f"Thông tin nhận diện Thảo:\n{_identity_block(refs, me_side, me_appearance, handed)}\n\n"
        f"Số liệu pose đo được (của người được cho là Thảo):\n{pose_text}\n\n"
        "Xác định Thảo, CHỈ phân tích Thảo, rồi trả JSON đúng schema."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text, "images": refs + images_b64},
        ],
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": {"temperature": 0.2, "num_ctx": VLM_NUM_CTX},
    }
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=900.0)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "{}")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"VLM trả về JSON không hợp lệ: {exc}: {content[:500]}")


def _pose_bbox(frame_rgb):
    """Bounding box (x0,y0,x1,y1 px) of the most prominent person, or None."""
    try:
        import mediapipe as mp
    except Exception:
        return None
    pose = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1,
                                  min_detection_confidence=0.5)
    try:
        res = pose.process(frame_rgb)
        lm = getattr(res, "pose_landmarks", None)
        if not lm:
            return None
        h, w = frame_rgb.shape[:2]
        xs = [p.x for p in lm.landmark if p.visibility is None or p.visibility > 0.3]
        ys = [p.y for p in lm.landmark if p.visibility is None or p.visibility > 0.3]
        if not xs or not ys:
            return None
        px, py = 0.08, 0.08  # padding
        x0 = max(0, int((min(xs) - px) * w)); x1 = min(w, int((max(xs) + px) * w))
        y0 = max(0, int((min(ys) - py) * h)); y1 = min(h, int((max(ys) + py) * h))
        if x1 - x0 < 10 or y1 - y0 < 10:
            return None
        return x0, y0, x1, y1
    finally:
        pose.close()


def _tighten_to_person(region):
    """Crop ``region`` to the detected person, but only if the box is a
    plausible person (a decent share of the region) — otherwise return the
    region unchanged so we never end up showing a sliver of background/wall."""
    box = _pose_bbox(region)
    if not box:
        return region
    h, w = region.shape[:2]
    x0, y0, x1, y1 = box
    area_frac = ((x1 - x0) * (y1 - y0)) / float(max(1, w * h))
    if area_frac < 0.15:  # too small → probably a false detection, keep the half
        return region
    return region[y0:y1, x0:x1]


def subject_crops(frames_rgb: list, side: str, want: int = 3) -> list[str]:
    """A few reference crops of the user from labelled frames: crop to the
    user's side, then tighten to the person when confidently detected."""
    if not frames_rgb:
        return []
    picks = [frames_rgb[i] for i in _even_indices(len(frames_rgb), want)]
    out: list[str] = []
    for frame in picks:
        region = _tighten_to_person(crop_side(frame, side))
        if region.size:
            out.append(_to_jpeg_b64(region))
    return out


def analyze_file(path: str, clip_type: str, model: str | None = None, *,
                 me_side: str = "", me_appearance: str = "", handed: str = "right",
                 reference_images_b64: list[str] | None = None) -> dict[str, Any]:
    """Full pipeline for one clip. Returns
    {model, frames_sampled, pose, raw, summary, ref_crops_b64}."""
    model = model or DEFAULT_VLM_MODEL
    pose_frames, vlm_frames = _sample_frames(path)
    if not vlm_frames:
        raise RuntimeError("Không đọc được khung hình nào từ clip (file hỏng hoặc định dạng lạ).")

    # Pose locks onto the user only when we know their side; else best-effort.
    cropped = me_side in _SIDE_VI
    pose_input = [crop_side(f, me_side) for f in pose_frames] if cropped else pose_frames
    pose = run_pose(pose_input)
    if cropped and pose.get("available"):
        pose["note"] = f"đo trên vùng {_SIDE_VI[me_side]} (đã cắt về phía Thảo)"
    elif not cropped:
        pose["note"] = "đo trên người nổi bật trong khung (chưa biết phía Thảo)"

    images_b64 = [_to_jpeg_b64(f) for f in vlm_frames]
    raw = call_vlm(
        images_b64, pose_to_text(pose), clip_type, model,
        reference_images_b64=reference_images_b64, me_side=me_side,
        me_appearance=me_appearance, handed=handed,
    )
    # Auto-build references only from labelled clips (we trust the side here).
    ref_crops_b64 = subject_crops(pose_frames, me_side) if cropped else []
    return {
        "model": model,
        "frames_sampled": len(vlm_frames),
        "pose": pose,
        "raw": raw,
        "summary": raw.get("summary", ""),
        "ref_crops_b64": ref_crops_b64,
    }


# ----------------------------------------------------- detection (step 1 VLM)
DETECT_MAX_FRAMES = 6
DETECT_SYSTEM_PROMPT = (
    "Bạn là trợ lý phân tích bóng bàn. NHIỆM VỤ DUY NHẤT ở bước này là XÁC ĐỊNH đâu là "
    "vận động viên Nguyễn Bá Thảo trong clip (KHÔNG phân tích kỹ thuật). Dựa vào ảnh tham "
    "chiếu (nếu có) và gợi ý (vị trí, màu áo, tay thuận). Trả về: identified (có chắc chắn "
    "tìm ra Thảo không), confidence 0..1, side (Thảo ở phía nào của khung: left/right/top/"
    "bottom, hoặc unknown nếu không rõ), appearance (mô tả ngắn trang phục Thảo), subject "
    "(mô tả ngắn người bạn cho là Thảo: vị trí + trang phục). Nếu không chắc, đặt "
    "identified=false và side=unknown. Chỉ trả JSON đúng schema, không thêm gì khác."
)
DETECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "identified": {"type": "boolean"},
        "confidence": {"type": "number"},
        "side": {"type": "string", "enum": ["left", "right", "top", "bottom", "unknown"]},
        "appearance": {"type": "string"},
        "subject": {"type": "string"},
    },
    "required": ["identified", "confidence", "side", "appearance", "subject"],
}


def detect_subject(path: str, *, reference_images_b64: list[str] | None = None,
                   me_side: str = "", me_appearance: str = "",
                   handed: str = "right", model: str | None = None) -> dict[str, Any]:
    """Step 1: a light VLM call that only locates Nguyễn Bá Thảo (no analysis)."""
    model = model or DEFAULT_VLM_MODEL
    _, vlm_frames = _sample_frames(path)
    if not vlm_frames:
        raise RuntimeError("Không đọc được khung hình nào từ clip.")
    frames = [vlm_frames[i] for i in _even_indices(len(vlm_frames), DETECT_MAX_FRAMES)]
    images_b64 = [_to_jpeg_b64(f) for f in frames]
    refs = (reference_images_b64 or [])[:REF_MAX]
    user_text = (
        f"Có {len(refs)} ảnh tham chiếu (nếu >0) rồi đến {len(images_b64)} khung hình clip.\n\n"
        f"Thông tin nhận diện:\n{_identity_block(refs, me_side, me_appearance, handed)}\n\n"
        "Hãy XÁC ĐỊNH đâu là Thảo (chưa phân tích). Trả JSON đúng schema."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DETECT_SYSTEM_PROMPT},
            {"role": "user", "content": user_text, "images": refs + images_b64},
        ],
        "stream": False,
        "format": DETECT_SCHEMA,
        "options": {"temperature": 0.1, "num_ctx": VLM_NUM_CTX},
    }
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=600.0)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "{}")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"VLM (detect) trả JSON không hợp lệ: {exc}: {content[:300]}")


def representative_frame_rgb(path: str):
    """The middle sampled frame — the canvas the user annotates a box on."""
    _, vlm_frames = _sample_frames(path)
    if not vlm_frames:
        return None
    return vlm_frames[len(vlm_frames) // 2]


def _to_jpeg_bytes(frame_rgb, max_dim: int = 1280, quality: int = 88) -> bytes:
    import cv2

    h, w = frame_rgb.shape[:2]
    scale = max_dim / max(h, w)
    if scale < 1:
        frame_rgb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)))
    bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def frame_jpeg(path: str) -> bytes | None:
    """Full representative frame as JPEG, for the box-annotation GUI."""
    frame = representative_frame_rgb(path)
    return _to_jpeg_bytes(frame, max_dim=1280) if frame is not None else None


def crop_box_jpeg(path: str, x: float, y: float, w: float, h: float) -> bytes | None:
    """Crop a user-drawn box (normalised 0..1) from the representative frame."""
    frame = representative_frame_rgb(path)
    if frame is None:
        return None
    H, W = frame.shape[:2]
    x0 = max(0, min(W - 1, int(x * W)))
    y0 = max(0, min(H - 1, int(y * H)))
    x1 = max(x0 + 1, min(W, int((x + w) * W)))
    y1 = max(y0 + 1, min(H, int((y + h) * H)))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return _to_jpeg_bytes(frame[y0:y1, x0:x1], max_dim=640, quality=90)


def make_preview_b64(path: str, side: str) -> str | None:
    """A crop of the user's side of a representative frame, for visual confirm.
    Shows the whole labelled half (which is guaranteed to contain the user);
    only tightens to the person when confidently detected. Returns JPEG-b64."""
    _, vlm_frames = _sample_frames(path)
    if not vlm_frames:
        return None
    frame = vlm_frames[len(vlm_frames) // 2]
    region = _tighten_to_person(crop_side(frame, side))
    if region.size == 0:
        return None
    return _to_jpeg_b64(region)


# --------------------------------------------------- profile synthesis (text)
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
    """Use a local text model to fold all accumulated traits into the profile
    summary fields. Returns a dict matching the summary columns."""
    if not traits:
        raise RuntimeError("Chưa có nhận xét (trait) nào để tổng hợp hồ sơ.")
    bullet = "\n".join(
        f"- [{t['aspect']} / {t['polarity']}] {t['text']}" for t in traits
    )
    user_text = (
        "Đây là hồ sơ một vận động viên bóng bàn tên Nguyễn Bá Thảo.\n"
        f"Thông tin cơ bản: thuận tay {basics.get('handed')}, cách cầm vợt "
        f"{basics.get('grip')}, lối đánh {basics.get('style') or 'chưa rõ'}.\n\n"
        f"Các nhận xét đã tích lũy từ nhiều clip:\n{bullet}\n\n"
        "Hãy tổng hợp thành hồ sơ súc tích bằng tiếng Việt, gộp các ý trùng lặp, "
        "nêu xu hướng nổi bật. Trả về JSON đúng schema."
    )
    payload = {
        "model": DEFAULT_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "Bạn là HLV bóng bàn, viết hồ sơ học trò bằng tiếng Việt."},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "format": _PROFILE_SCHEMA,
        "options": {"temperature": 0.3, "num_ctx": 8192},
    }
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=600.0)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "{}")
    return json.loads(content)


# --------------------------------------------------- skill ledger synthesis
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
}


def synthesize_skills(
    basics: dict[str, Any], findings_by_aspect: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Use the local text model to turn the accepted findings into a skill
    ledger: a 1–10 rating + status + assessment + improvement priority per
    aspect. Only aspects that have findings are scored. Returns a list of dicts.

    The rating is the model's estimate FROM THE WRITTEN FINDINGS — a reference,
    not a calibrated score; the user can override it afterwards."""
    if not findings_by_aspect:
        raise RuntimeError("Chưa có nhận xét đã duyệt nào để dựng hồ sơ kỹ năng.")
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
        f"đánh {basics.get('style') or 'chưa rõ'}), gom theo từng mảng kỹ năng:\n\n"
        f"{body}\n\n"
        "Với MỖI mảng có nhận xét ở trên, hãy đánh giá bằng tiếng Việt:\n"
        "- rating: điểm 1–10 (ước lượng trình độ mảng đó dựa trên các nhận xét; "
        "10 = rất tốt, 1 = rất yếu).\n"
        "- status: strength (điểm mạnh) / weakness (điểm yếu) / improving (đang "
        "tiến bộ) / needs_work (cần cải thiện nhiều) / neutral.\n"
        "- assessment: 1–2 câu súc tích mô tả trình độ mảng đó.\n"
        "- priority: mức ưu tiên cần luyện (1 = ưu tiên cao nhất; 0 = không cần ưu tiên). "
        "Mảng càng yếu/quan trọng thì priority càng nhỏ (1,2,3...).\n"
        f"Chỉ chấm các mảng sau: {aspects_list}. Trả về JSON đúng schema."
    )
    payload = {
        "model": DEFAULT_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "Bạn là HLV bóng bàn, đánh giá trình độ học trò bằng tiếng Việt."},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "format": _SKILLS_SCHEMA,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=600.0)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "{}")
    data = json.loads(content)
    return data.get("skills", []) if isinstance(data, dict) else []


# ------------------------------------------------------------------- health
def check_models() -> dict[str, Any]:
    """Probe Ollama: is it up, and which models are pulled?"""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        up = True
    except Exception:
        return {
            "ollama_up": False,
            "models": [],
            "default_model": DEFAULT_VLM_MODEL,
            "default_available": False,
            "message": "Không kết nối được Ollama. Hãy chắc chắn Ollama đang chạy (ollama serve).",
        }
    available = DEFAULT_VLM_MODEL in models
    msg = "OK" if available else (
        f"Ollama đang chạy nhưng thiếu model '{DEFAULT_VLM_MODEL}'. "
        f"Chạy: ollama pull {DEFAULT_VLM_MODEL}"
    )
    return {
        "ollama_up": up,
        "models": models,
        "default_model": DEFAULT_VLM_MODEL,
        "default_available": available,
        "message": msg,
    }
