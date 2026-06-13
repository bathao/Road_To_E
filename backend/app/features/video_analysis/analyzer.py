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
from app.features.video_analysis import ball as ball_tracker

# How many frames to feed each stage. The VLM set is a subset (token/VRAM
# budget); pose can look at more frames since it is cheap on CPU.
VLM_MAX_FRAMES = 14
POSE_MAX_FRAMES = 48      # default frame budget (detect step; short clips)
VLM_MAX_STROKES = 5       # per-stroke montages sent to the VLM (token budget)
VLM_CONTEXT_FRAMES = 2    # whole-frame context shots alongside the montages
# Deep analysis samples by DURATION, not a fixed count: a fixed 48 frames over a
# 3-min clip is ~0.27 fps — far too sparse to see strokes (and makes fps-dependent
# metrics meaningless). Aim for ~this many fps, between a floor and a CPU-bounded
# cap (MediaPipe pose runs per frame on CPU).
SAMPLE_TARGET_FPS = 6.0
POSE_MIN_FRAMES = 48
POSE_CAP_FRAMES = 220
FRAME_MAX_DIM = 768  # downscale longest side before sending to the VLM
# Each frame costs ~1k vision tokens, so 14 frames + prompt + output blows past
# Ollama's 4096 default. Give the VLM a large window; an 8B model + this KV
# cache still fits comfortably in 16GB VRAM.
VLM_NUM_CTX = 32768

# BlazePose (MediaPipe) landmark indices we use.
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
L_WRIST, R_WRIST = 15, 16

# Min shoulder-width / torso-length for a frame to count as "front-facing enough"
# to trust width ratios (below this the player is too side-on → ratios explode).
_FRONT_FACING_MIN = 0.33


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


# ------------------------------------------------------------- audio (S2)
AUDIO_SR = 16000  # mono sample rate for impact detection


def extract_audio_pcm(path: str, sr: int = AUDIO_SR):
    """Decode the clip's audio to mono float32 PCM in [-1, 1] via ffmpeg. Returns
    a numpy array, or None if the clip has no audio / ffmpeg fails. Raw s16le over
    a pipe — no header parsing, no temp file."""
    import numpy as np

    ff = _ffmpeg_bin()
    cmd = [ff, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr),
           "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"]
    proc = subprocess.run(cmd, capture_output=True)  # binary stdout (no text=True)
    if proc.returncode != 0 or not proc.stdout:
        return None
    pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return pcm if pcm.size else None


def detect_impacts(path: str, sr: int = AUDIO_SR) -> list[float]:
    """S2 — detect ball-contact 'tock' onsets from the clip audio: a cheap,
    vision-independent timing anchor for stroke phasing (S4) and tempo. Returns
    impact times in seconds (ascending), or [] if there is no audio / none found.
    Best-effort: any failure → [] so it never blocks analysis.

    Method: emphasise high-frequency transients (first difference ≈ high-pass),
    take short-time energy, then onset = positive energy flux; keep adaptive-
    threshold peaks at least 80 ms apart."""
    try:
        pcm = extract_audio_pcm(path, sr)
    except Exception:
        return []
    if pcm is None or pcm.size < sr // 5:  # < 0.2 s of audio → nothing useful
        return []
    import numpy as np

    emph = np.diff(pcm, prepend=pcm[:1])          # crude high-pass
    hop = max(1, sr // 100)                        # 10 ms frames
    win = hop * 2
    n = (len(emph) - win) // hop
    if n <= 2:
        return []
    sq = emph.astype(np.float64) ** 2
    csum = np.concatenate(([0.0], np.cumsum(sq)))  # prefix sums → fast windows
    starts = np.arange(n) * hop
    energy = (csum[starts + win] - csum[starts]).astype(np.float64)

    flux = np.diff(energy, prepend=energy[:1])
    flux[flux < 0] = 0.0
    if flux.max() <= 0:
        return []
    thr = flux.mean() + 2.5 * flux.std()
    min_gap = max(1, int(0.08 * sr / hop))         # ≥ 80 ms between impacts

    impacts: list[float] = []
    last = -(10 ** 9)
    for i in range(1, n - 1):
        if flux[i] >= thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]:
            if i - last >= min_gap:
                impacts.append(round(i * hop / sr, 3))
                last = i
    return impacts


# --------------------------------- audio cross-validation / activity (S2 + B)
def motion_energy(frames_ts: list[tuple[float, Any]]) -> list[tuple[float, float]]:
    """Per-frame motion energy (mean absolute frame-difference) within the given
    region — fed the player-cropped frames so it reflects the player moving, not
    the whole hall. Returns [(t, energy), ...] for the 2nd..Nth frames. Cheap CPU;
    frames are downscaled to a fixed size so differencing is shape-stable."""
    import cv2
    import numpy as np

    out: list[tuple[float, float]] = []
    prev = None
    for t, frame in frames_ts:
        g = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        g = cv2.resize(g, (128, 128))
        if prev is not None:
            out.append((t, float(np.abs(g.astype(np.int16) - prev.astype(np.int16)).mean())))
        prev = g
    return out


def corroborate_impacts(impacts: list[float], energy: list[tuple[float, float]],
                        *, window: float = 0.2) -> list[float]:
    """Keep only audio impacts that coincide with elevated motion in the player's
    region — a real contact by the subject moves their body, whereas a neighbour
    table's 'tock' lands while the subject is comparatively still. Rejects that
    cross-talk in noisy multi-table halls. Best-effort: with no energy signal it
    returns the impacts unchanged (never blocks)."""
    if not impacts or not energy:
        return impacts
    import statistics

    vals = [e for _, e in energy]
    thr = statistics.median(vals) + 0.5 * (statistics.pstdev(vals) if len(vals) > 1 else 0.0)
    kept: list[float] = []
    for t in impacts:
        near = [e for tt, e in energy if abs(tt - t) <= window]
        if near and max(near) >= thr:
            kept.append(t)
    return kept


def _even_indices(total: int, want: int) -> list[int]:
    """Evenly-spaced frame indices across [0, total)."""
    if total <= 0:
        return []
    if total <= want:
        return list(range(total))
    step = total / want
    return [min(total - 1, int(i * step)) for i in range(want)]


def sample_timestamped(path: str, max_frames: int) -> list[tuple[float, Any]]:
    """S1 — the single decode primitive. One pass over the video, evenly sampling
    up to ``max_frames`` frames, each paired with its timestamp in seconds
    (frame index / fps). This is the *only* place frames are read off disk; every
    downstream stage (pose, VLM sampling, previews) reuses the result, so the
    whole pipeline speaks in real seconds. Returns [(t_sec, frame_rgb), ...]."""
    import cv2

    cap = cv2.VideoCapture(path)
    out: list[tuple[float, Any]] = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0

        def t_of(idx: int) -> float:
            return round(idx / fps, 3) if fps else 0.0

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        idxs = _even_indices(total, max_frames) if total else []
        if idxs:
            for idx in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if ok and frame is not None:
                    out.append((t_of(idx), cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        else:
            # Unknown frame count: read sequentially, keep every Nth.
            grabbed = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                grabbed.append(frame)
            for idx in _even_indices(len(grabbed), max_frames):
                out.append((t_of(idx), cv2.cvtColor(grabbed[idx], cv2.COLOR_BGR2RGB)))
    finally:
        cap.release()
    return out


def decode_at_times(path: str, times: list[float]) -> list[tuple[float, Any]]:
    """Decode the frames nearest specific timestamps (seconds). Used to grab a
    tight window around each audio impact for impact-anchored montages, when
    pose-based stroke segmentation failed. Returns [(t_sec, frame_rgb), ...]."""
    import cv2

    cap = cv2.VideoCapture(path)
    out: list[tuple[float, Any]] = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        for t in times:
            idx = int(round(t * fps)) if fps else 0
            if total:
                idx = max(0, min(total - 1, idx))
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if ok and frame is not None:
                out.append((t, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    finally:
        cap.release()
    return out


def _sample_frames(path: str) -> tuple[list, list]:
    """Return (pose_frames_rgb, vlm_frames_rgb). Both are lists of RGB numpy
    arrays; the VLM list is an even subset of the pose list. Thin wrapper over
    :func:`sample_timestamped` (S1) — selection is identical to before."""
    pose_frames = [f for _, f in sample_timestamped(path, POSE_MAX_FRAMES)]
    # VLM subset: evenly pick from the pose frames.
    vlm = [pose_frames[i] for i in _even_indices(len(pose_frames), VLM_MAX_FRAMES)]
    return pose_frames, vlm


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
    """Mean/min/max after trimming outliers via a 1.5×IQR fence. Pose ratios still
    carry the odd bad-frame spike even after the front-facing guard; trimming keeps
    the reported mean/range honest rather than letting one 14× frame dominate."""
    if not values:
        return None
    xs = sorted(values)
    if len(xs) >= 4:
        n = len(xs)
        q1 = xs[n // 4]
        q3 = xs[(3 * n) // 4]
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        trimmed = [x for x in xs if lo <= x <= hi]
        if trimmed:
            xs = trimmed
    mean = sum(xs) / len(xs)
    return {
        "mean": round(mean, 1),
        "min": round(min(xs), 1),
        "max": round(max(xs), 1),
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

    def mean_of(metric: dict | None) -> float | None:
        return metric.get("mean") if metric else None

    measured = pose.get("measured_on")
    scope = ("(số dưới đây ĐO TRONG LÚC đánh bóng)" if measured == "strokes"
             else "(số đo trên toàn clip, gồm cả lúc đứng nghỉ — chỉ tham khảo)"
             if measured == "whole_clip" else "")

    # Pre-interpret the numbers in CODE and hand the VLM the verdict. An 8B VLM
    # reliably MISREADS raw pose numbers (e.g. it called knee 162.8° — nearly
    # straight — "khuỵu gối tốt, trọng tâm thấp", the exact opposite). We know the
    # thresholds, so we state the conclusion; the prompt tells the model to defer
    # to these verdicts rather than re-judge the number itself.
    knee = mean_of(pose.get("knee_flexion_deg"))
    if knee is None:
        knee_v = ""
    elif knee >= 160:
        knee_v = (" → ĐÁNH GIÁ: gối gần như THẲNG, KHÔNG hạ được trọng tâm — đây là ĐIỂM YẾU "
                  "cần khuỵu gối nhiều hơn, TUYỆT ĐỐI không khen là 'trọng tâm thấp/khuỵu gối tốt'.")
    elif knee >= 148:
        knee_v = " → ĐÁNH GIÁ: gối khuỵu VỪA PHẢI, trọng tâm trung bình."
    else:
        knee_v = " → ĐÁNH GIÁ: gối khuỵu TỐT, trọng tâm thấp (điểm mạnh)."

    stance = mean_of(pose.get("stance_width_ratio"))
    if stance is None:
        stance_v = " (không đo được — người chơi xoay nghiêng, đừng nhận xét độ rộng tấn)."
    elif stance >= 1.4:
        stance_v = " → ĐÁNH GIÁ: tấn RỘNG, vững (điểm mạnh)."
    elif stance >= 1.0:
        stance_v = " → ĐÁNH GIÁ: tấn trung bình."
    else:
        stance_v = " → ĐÁNH GIÁ: tấn HẸP (nên đứng rộng chân hơn)."

    lean = mean_of(pose.get("torso_lean_deg"))
    lean_v = ""
    if lean is not None:
        lean_v = (" → ĐÁNH GIÁ: thân khá thẳng đứng." if lean < 12
                  else " → ĐÁNH GIÁ: thân nghiêng nhiều.")

    lines = [
        f"- Số khung phát hiện được người: {pose['frames_with_pose']}/{pose['frames_analyzed']} {scope}",
        f"- Độ rộng tấn (cổ chân / vai): {fmt(pose.get('stance_width_ratio'))}{stance_v}",
        f"- Góc gập gối: {fmt(pose.get('knee_flexion_deg'), '°')} (180°=thẳng){knee_v}",
        f"- Độ nghiêng thân: {fmt(pose.get('torso_lean_deg'), '°')}{lean_v}",
        f"- Biên độ di chuyển ngang của hông (bộ chân, đo trên CẢ clip): {pose.get('lateral_sway')} "
        "(theo tỉ lệ khung hình; càng lớn = di chuyển chân càng nhiều).",
        f"- Độ cao tay (so với vai, theo độ rộng vai): {fmt(pose.get('hand_elevation'))}.",
    ]
    dyn = pose.get("dynamics") or {}
    if dyn:
        parts = [f"{dyn.get('n_strokes', 0)} cú đánh tách được"]
        if dyn.get("swing_speed"):
            parts.append(f"tốc độ vung (đỉnh cổ tay, tương đối) TB {dyn['swing_speed']['mean']}")
        if dyn.get("tempo_sec") is not None:
            parts.append(f"nhịp ~{dyn['tempo_sec']}s/cú")
        if dyn.get("recovery_sec") is not None:
            parts.append(f"thời gian hồi vị giữa các cú TB ~{dyn['recovery_sec']}s")
        lines.append("- Động lực cú đánh: " + "; ".join(parts) + ".")
    return "\n".join(lines)


def pose_to_metrics(pose: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten aggregate pose metrics into the flat ``{name, value, unit}`` rows
    the time-series store (``va_metric``) will hold. Additive scaffolding: not
    persisted yet, but the canonical shape so progress tracking (Phase 3) can
    compare clips over time. Only the mean of each metric is emitted here (the
    min/max stay in ``pose_json``)."""
    if not pose.get("available") or not pose.get("frames_with_pose"):
        return []
    out: list[dict[str, Any]] = []

    def add_mean(name: str, metric: dict | None, unit: str = "") -> None:
        if metric and metric.get("mean") is not None:
            out.append({"name": name, "value": float(metric["mean"]), "unit": unit})

    add_mean("stance_width_ratio_mean", pose.get("stance_width_ratio"))
    add_mean("knee_flexion_deg_mean", pose.get("knee_flexion_deg"), "deg")
    add_mean("torso_lean_deg_mean", pose.get("torso_lean_deg"), "deg")
    add_mean("hand_elevation_mean", pose.get("hand_elevation"))
    if pose.get("lateral_sway") is not None:
        out.append({"name": "lateral_sway", "value": float(pose["lateral_sway"]), "unit": "frac"})
    dyn = pose.get("dynamics") or {}
    if dyn.get("swing_speed") and dyn["swing_speed"].get("mean") is not None:
        out.append({"name": "swing_speed_mean", "value": float(dyn["swing_speed"]["mean"]), "unit": "norm/s"})
    if dyn.get("tempo_sec") is not None:
        out.append({"name": "tempo_sec", "value": float(dyn["tempo_sec"]), "unit": "s"})
    if dyn.get("recovery_sec") is not None:
        out.append({"name": "recovery_sec", "value": float(dyn["recovery_sec"]), "unit": "s"})
    return out


# ------------------------------------------- unified pose pass (S3, one MediaPipe run)
def analyze_pose(frames_ts: list[tuple[float, Any]], handed: str = "right"
                 ) -> tuple[list[dict[str, Any]], int, bool, str]:
    """ONE MediaPipe pass over (t, frame): produces per-frame records used for
    BOTH stroke segmentation (wrist trajectory) and aggregate biomechanics —
    replacing the old run_pose + pose_track double pass. Each record holds
    ``{t, wx, wy, wvis, cx, stance, knee, lean, hip_x, hand_elev}`` (metric fields
    are None when their landmarks aren't visible). Returns
    ``(records, frames_with_pose, available, reason)``."""
    try:
        import mediapipe as mp
    except Exception as exc:  # pragma: no cover - install guard
        return [], 0, False, f"mediapipe unavailable: {exc}"
    if not frames_ts:
        return [], 0, False, "no frames"

    wrist_i = playing_wrist_index(handed)
    pose = mp.solutions.pose.Pose(
        static_image_mode=True, model_complexity=1, min_detection_confidence=0.5
    )
    records: list[dict[str, Any]] = []
    try:
        for t, frame in frames_ts:
            res = pose.process(frame)
            lm = getattr(res, "pose_landmarks", None)
            if not lm:
                continue
            pts = lm.landmark

            def vis(i: int) -> bool:
                return pts[i].visibility is None or pts[i].visibility > 0.3

            shoulder_w = _dist(pts[L_SHOULDER], pts[R_SHOULDER]) or 1e-6
            sh_mid_y = (pts[L_SHOULDER].y + pts[R_SHOULDER].y) / 2
            hip_mid_x = (pts[L_HIP].x + pts[R_HIP].x) / 2
            hip_mid_y = (pts[L_HIP].y + pts[R_HIP].y) / 2
            sh_mid_x = (pts[L_SHOULDER].x + pts[R_SHOULDER].x) / 2

            w = pts[wrist_i]
            knees = [
                _angle(pts[hip], pts[knee], pts[ankle])
                for hip, knee, ankle in ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE))
                if vis(hip) and vis(knee) and vis(ankle)
            ]
            # Rotation guard: ratios normalised by 2D shoulder width blow up when the
            # player turns side-on (shoulder width collapses toward 0 → stance/hand
            # ratios explode, e.g. 14×). Torso length (shoulder-mid → hip-mid) barely
            # changes under that yaw, so when shoulders are narrow relative to the
            # torso the frame is too side-on to measure width ratios → record None
            # (knee angle and lean are rotation-stable, so they're always kept).
            torso = math.hypot(sh_mid_x - hip_mid_x, sh_mid_y - hip_mid_y) or 1e-6
            front_facing = (shoulder_w / torso) >= _FRONT_FACING_MIN
            hand_el = [(sh_mid_y - pts[wr].y) / shoulder_w for wr in (L_WRIST, R_WRIST) if vis(wr)]
            records.append({
                "t": round(t, 3),
                "wx": w.x, "wy": w.y,
                "wvis": w.visibility if w.visibility is not None else 1.0,
                "cx": sh_mid_x,
                "stance": (_dist(pts[L_ANKLE], pts[R_ANKLE]) / shoulder_w)
                          if (front_facing and vis(L_ANKLE) and vis(R_ANKLE)) else None,
                "knee": (sum(knees) / len(knees)) if knees else None,
                "lean": abs(math.degrees(math.atan2(sh_mid_x - hip_mid_x, -(sh_mid_y - hip_mid_y)))),
                "hip_x": hip_mid_x,
                "hand_elev": (sum(hand_el) / len(hand_el)) if (front_facing and hand_el) else None,
            })
    finally:
        pose.close()
    return records, len(records), True, ""


def aggregate_pose(records: list[dict[str, Any]], total_frames: int,
                   intervals: list[tuple[float, float]] | None = None) -> dict[str, Any]:
    """Aggregate per-frame pose records into the metric dict (same shape as the
    old run_pose). When ``intervals`` (stroke [t_start, t_end] windows) are given,
    metrics are measured ONLY on frames inside them — i.e. during actual strokes,
    not idle standing, which otherwise drags e.g. knee angle toward "legs straight".
    Falls back to all frames when there's no usable overlap."""
    if not records:
        return {"available": True, "frames_analyzed": total_frames,
                "frames_with_pose": 0, "reason": "no body detected in sampled frames"}
    use, scoped = records, False
    if intervals:
        inside = [r for r in records if any(t0 <= r["t"] <= t1 for t0, t1 in intervals)]
        if len(inside) >= 3:
            use, scoped = inside, True
    # Posture metrics (stance/knee/lean/hand) reflect the moment of the stroke →
    # measure on the scoped frames. But lateral sway is FOOTWORK RANGE, which
    # happens BETWEEN strokes (moving to the ball) — measuring it only within a
    # stroke window makes it tiny and falsely flags footwork as weak. So sway is
    # always measured across the whole clip.
    all_hip_xs = [r["hip_x"] for r in records if r["hip_x"] is not None]
    return {
        "available": True,
        "frames_analyzed": total_frames,
        "frames_with_pose": len(records),
        "frames_measured": len(use),
        "measured_on": "strokes" if scoped else "whole_clip",
        "stance_width_ratio": _stats([r["stance"] for r in use if r["stance"] is not None]),
        "knee_flexion_deg": _stats([r["knee"] for r in use if r["knee"] is not None]),
        "torso_lean_deg": _stats([r["lean"] for r in use if r["lean"] is not None]),
        "lateral_sway": round(max(all_hip_xs) - min(all_hip_xs), 3) if all_hip_xs else None,
        "hand_elevation": _stats([r["hand_elev"] for r in use if r["hand_elev"] is not None]),
    }


# ----------------------------------------- stroke segmentation + phasing (S4)
def playing_wrist_index(handed: str) -> int:
    return L_WRIST if handed == "left" else R_WRIST


def playing_elbow_index(handed: str) -> int:
    return L_ELBOW if handed == "left" else R_ELBOW


def playing_shoulder_index(handed: str) -> int:
    return L_SHOULDER if handed == "left" else R_SHOULDER


def _guess_hand(wx: float, cx: float, handed: str) -> str:
    """Best-effort forehand/backhand from wrist-x vs body centre. Camera
    orientation is unknown, so this is a guess, not ground truth — callers should
    treat it as a hint and let the VLM/user correct it."""
    off = wx - cx
    if abs(off) < 0.05:
        return "unknown"
    # For a right-hander the forehand wing sits to body-right in a front view;
    # mirror for left-handers.
    return "forehand" if (off > 0) == (handed != "left") else "backhand"


def segment_strokes(series: list[dict[str, Any]], impacts: list[float] | None = None,
                    *, handed: str = "right", min_gap_s: float = 0.3,
                    k: float = 0.7) -> list[dict[str, Any]]:
    """S4 — split the playing-wrist trajectory into strokes and canonical phases.
    A stroke is a burst of high wrist speed; its **contact instant snaps to the
    nearest audio impact** (S2) when one is within 150 ms, else the speed peak.
    Phase boundaries are the speed valleys around the peak. Returns ordered
    strokes: ``{idx, t_start, t_contact, t_end, hand, peak_speed, phases}``.

    Heuristic and resolution-bound: coarse frame sampling caps timing precision,
    and ``hand`` is a best-effort guess (see :func:`_guess_hand`)."""
    if len(series) < 3:
        return []
    spd: list[tuple[float, float, int]] = []  # (t, speed, index into series)
    for i in range(1, len(series)):
        dt = series[i]["t"] - series[i - 1]["t"]
        if dt <= 0:
            continue
        d = math.hypot(series[i]["wx"] - series[i - 1]["wx"],
                       series[i]["wy"] - series[i - 1]["wy"])
        spd.append((series[i]["t"], d / dt, i))
    if len(spd) < 3:
        return []
    speeds = [s for _, s, _ in spd]
    mean, std = _mean_std(speeds)
    thr = mean + k * std
    valley = mean  # below the mean ≈ between strokes
    impacts = impacts or []

    strokes: list[dict[str, Any]] = []
    last_contact = -1e9
    for j in range(1, len(spd) - 1):
        t, s, i = spd[j]
        if not (s >= thr and s >= spd[j - 1][1] and s >= spd[j + 1][1]):
            continue
        if t - last_contact < min_gap_s:
            continue
        a = j
        while a > 0 and spd[a][1] > valley:
            a -= 1
        b = j
        while b < len(spd) - 1 and spd[b][1] > valley:
            b += 1
        t_start, t_end = spd[a][0], spd[b][0]
        t_contact = t
        if impacts:
            near = min(impacts, key=lambda im: abs(im - t))
            if abs(near - t) <= 0.15:
                t_contact = near
        hand = _guess_hand(series[i]["wx"], series[i]["cx"], handed)
        mid = (t_start + t_contact) / 2
        strokes.append({
            "idx": len(strokes),
            "t_start": round(t_start, 3),
            "t_contact": round(t_contact, 3),
            "t_end": round(t_end, 3),
            "hand": hand,
            "peak_speed": round(s, 4),
            "phases": {
                "backswing": [round(t_start, 3), round(mid, 3)],
                "forward_swing": [round(mid, 3), round(t_contact, 3)],
                "contact": [round(t_contact, 3), round(t_contact, 3)],
                "follow_through": [round(t_contact, 3), round(t_end, 3)],
            },
        })
        last_contact = t_contact
    return strokes


def _mean_std(xs: list[float]) -> tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / len(xs)
    return m, math.sqrt(var)


def stroke_dynamics(strokes: list[dict[str, Any]]) -> dict[str, Any]:
    """Dynamic, stroke-level biomechanics derived from the segmented strokes —
    the things a coach actually talks about, beyond static posture:
    - swing_speed: peak playing-wrist speed per stroke (normalised coords/sec; a
      RELATIVE measure, comparable across this player's clips, not an absolute m/s).
    - tempo_sec: mean time between consecutive ball contacts.
    - recovery_sec: mean gap between a stroke ending and the next one starting
      (readiness / how fast they reset between shots).
    Empty dict when there aren't enough strokes."""
    if not strokes:
        return {}
    ordered = sorted(strokes, key=lambda s: s["t_contact"])
    out: dict[str, Any] = {
        "n_strokes": len(strokes),
        "swing_speed": _stats([s["peak_speed"] for s in strokes]),
    }
    contacts = [s["t_contact"] for s in ordered]
    if len(contacts) >= 2:
        tempos = [contacts[i] - contacts[i - 1] for i in range(1, len(contacts))]
        out["tempo_sec"] = round(sum(tempos) / len(tempos), 2)
    gaps = [ordered[i]["t_start"] - ordered[i - 1]["t_end"] for i in range(1, len(ordered))]
    gaps = [g for g in gaps if g >= 0]
    if gaps:
        out["recovery_sec"] = round(sum(gaps) / len(gaps), 2)
    return out


# ----------------------------------------------------- stroke montages (S6)
MONTAGE_CELL_MAX = 384  # longest side of each cell in a montage strip


def frame_at_time(frames_ts: list[tuple[float, Any]], t: float):
    """Nearest sampled frame to timestamp ``t`` (or None if no frames)."""
    if not frames_ts:
        return None
    return min(frames_ts, key=lambda ft: abs(ft[0] - t))[1]


def montage_strip(frames_rgb: list, cell_max: int = MONTAGE_CELL_MAX) -> str | None:
    """Concatenate frames left→right into one image (a swing read in a single
    picture), returned as JPEG base64. Cells are scaled to ``cell_max`` on their
    longest side and bottom-padded to a common height. None if no frames."""
    import cv2
    import numpy as np

    cells = []
    for f in frames_rgb:
        if f is None or getattr(f, "size", 0) == 0:
            continue
        h, w = f.shape[:2]
        scale = cell_max / max(h, w)
        if scale < 1:
            f = cv2.resize(f, (int(w * scale), int(h * scale)))
        cells.append(f)
    if not cells:
        return None
    height = max(c.shape[0] for c in cells)
    padded = []
    for c in cells:
        if c.shape[0] < height:
            pad = np.zeros((height - c.shape[0], c.shape[1], 3), dtype=c.dtype)
            c = np.vstack([c, pad])
        padded.append(c)
    strip = np.hstack(padded)
    bgr = cv2.cvtColor(strip, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else None


def stroke_montage_b64(frames_ts: list[tuple[float, Any]],
                       stroke: dict[str, Any]) -> str | None:
    """One montage per stroke: backswing → forward-swing → contact → follow-
    through frames (nearest sampled frames to each phase time)."""
    times = [
        stroke["t_start"],
        stroke["phases"]["forward_swing"][0],
        stroke["t_contact"],
        stroke["t_end"],
    ]
    frames = [frame_at_time(frames_ts, t) for t in times]
    return montage_strip([f for f in frames if f is not None])


# --------------------------------------- annotated evidence thumbnails (NC4a)
EVIDENCE_MAX_DIM = 480  # longest side of a saved evidence thumbnail
_HAND_SHORT = {"forehand": "FH", "backhand": "BH"}


def annotate_pose_frame(frame_rgb, handed: str = "right", *, hand: str = "",
                        t: float | None = None) -> str | None:
    """Draw the pose skeleton + the playing-arm elbow and knee angles on one frame
    — a user-facing *evidence* thumbnail for the moment a finding refers to, so the
    user can SEE the geometry, not just read a sentence (NC4a). Pure geometry; the
    caption is ASCII (the cv2 Hershey font has no Vietnamese glyphs). Returns
    annotated JPEG b64, or None if the frame/libs are unusable. Skeleton is skipped
    gracefully when no body is detected (the raw frame + caption still ship)."""
    if frame_rgb is None or getattr(frame_rgb, "size", 0) == 0:
        return None
    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return None
    # Zoom to the player first: the side-crop of a 4K frame leaves the subject tiny
    # and the skeleton hair-thin after downscaling. Cropping to the pose bbox makes
    # the evidence legible (and is what the user wants to see — themselves, close).
    box = _pose_bbox(frame_rgb)
    region = frame_rgb[box[1]:box[3], box[0]:box[2]] if box else frame_rgb
    pose = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1,
                                  min_detection_confidence=0.5)
    try:
        res = pose.process(region)
        lm = getattr(res, "pose_landmarks", None)
        bgr = cv2.cvtColor(region, cv2.COLOR_RGB2BGR).copy()
        knee_txt = elbow_txt = ""
        if lm:
            mp.solutions.drawing_utils.draw_landmarks(
                bgr, lm, mp.solutions.pose.POSE_CONNECTIONS,
                mp.solutions.drawing_utils.DrawingSpec((0, 230, 0), 2, 2),
                mp.solutions.drawing_utils.DrawingSpec((0, 170, 255), 2),
            )
            pts = lm.landmark

            def visible(i: int) -> bool:
                return pts[i].visibility is None or pts[i].visibility > 0.3

            si, ei, wi = (playing_shoulder_index(handed), playing_elbow_index(handed),
                          playing_wrist_index(handed))
            if visible(si) and visible(ei) and visible(wi):
                elbow_txt = f"elbow={round(_angle(pts[si], pts[ei], pts[wi]))}"
            knees = [_angle(pts[h], pts[k], pts[a])
                     for h, k, a in ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE))
                     if visible(h) and visible(k) and visible(a)]
            if knees:
                knee_txt = f"knee={round(sum(knees) / len(knees))}"
        cap = " ".join(x for x in [
            f"t={t:.2f}s" if t is not None else "",
            _HAND_SHORT.get(hand, ""), knee_txt, elbow_txt,
        ] if x)
        if cap:
            h, w = bgr.shape[:2]
            cv2.rectangle(bgr, (0, h - 22), (w, h), (0, 0, 0), -1)
            cv2.putText(bgr, cap, (6, h - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)
        H, W = bgr.shape[:2]
        scale = EVIDENCE_MAX_DIM / max(H, W)
        if scale < 1:
            bgr = cv2.resize(bgr, (int(W * scale), int(H * scale)))
        ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buf.tobytes()).decode("ascii") if ok else None
    finally:
        pose.close()


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
    "PHONG CÁCH BẮT BUỘC: bạn là HLV KHÓ TÍNH, tiêu chuẩn thi đấu CAO, phân tích NGHIÊM KHẮC và "
    "thẳng thắn. TUYỆT ĐỐI KHÔNG khen xã giao/nịnh bợ, không dùng lời khen chung chung ('tốt', 'ổn', "
    "'linh hoạt', 'chuẩn') khi không có bằng chứng rõ ràng. MẶC ĐỊNH soi LỖI và điểm cần sửa; chỉ xếp "
    "là điểm mạnh khi kỹ thuật THẬT SỰ nổi bật và thấy rõ trong hình — nếu chỉ ở mức bình thường/khá "
    "thì KHÔNG tính là điểm mạnh (để trống còn hơn khen hời hợt). Ưu tiên số điểm yếu nhiều hơn điểm "
    "mạnh nếu thực tế là vậy. Mỗi điểm yếu PHẢI kèm sai ở đâu và cách sửa cụ thể. Phần 'summary' viết "
    "thẳng thắn, nêu VẤN ĐỀ CHÍNH cần khắc phục, không tô hồng. "
    "Trả lời HOÀN TOÀN bằng tiếng Việt, cụ thể, mang tính huấn luyện. Chỉ trả JSON đúng schema, "
    "không thêm chữ nào ngoài JSON. Mục nào không quan sát rõ thì ghi 'không quan sát rõ', không bịa. "
    "KHÔNG liệt kê cùng một mảng (vd bộ chân, thuận tay) vừa là điểm mạnh vừa là điểm yếu với cùng "
    "một lý do. Số liệu pose chỉ là THAM KHẢO (đo tự động, có thể nhiễu); ưu tiên quan sát diễn tiến "
    "động tác trong các ảnh ghép, nếu số pose mâu thuẫn với hình thì tin vào hình. "
    "QUAN TRỌNG: khi phần số liệu pose có dòng 'ĐÁNH GIÁ: ...' thì đó là kết luận ĐÚNG về hình học "
    "cơ thể (đã tính sẵn bằng công thức), bạn PHẢI tuân theo và KHÔNG được nói ngược lại — ví dụ nếu "
    "ĐÁNH GIÁ nói gối gần thẳng/trọng tâm cao thì TUYỆT ĐỐI không được khen 'khuỵu gối tốt, trọng tâm thấp'. "
    "Nếu một mảng KHÔNG quan sát rõ thì ĐỪNG đưa vào strengths/weaknesses; chỉ ghi 'không quan sát rõ' "
    "ở trường notes tương ứng (serve/footwork/posture) hoặc bỏ trống. "
    "Ngoài kỹ thuật, hãy nhận xét ĐỊNH TÍNH (không cần đếm con số): trường 'serve_variety'.notes = "
    "độ ĐA DẠNG giao bóng (có thay đổi giao ngắn/dài, xoáy, điểm rơi hay đơn điệu/dễ đoán); "
    "'tactics'.notes = xu hướng CHIẾN THUẬT quan sát được (chọn cú, dựng điểm, hay tấn công/phòng thủ, "
    "điểm rơi ưa dùng) VÀ chỉ thẳng LỖ HỔNG chiến thuật (đơn điệu, dễ đoán, dễ bị bắt bài) chứ không "
    "chỉ khen. Chỉ mô tả những gì THẤY trong các ảnh ghép; KHÔNG bịa số liệu thắng/thua, "
    "KHÔNG đếm winner/lỗi (không đủ dữ liệu). Mảng nào không thấy rõ thì ghi 'không quan sát rõ'. "
    "Với MỖI điểm mạnh/yếu, điền t_ref = giây trong clip nơi bạn quan sát thấy (dựa vào thời điểm các "
    "cú đánh đã cung cấp; để 0 nếu không xác định được) và confidence = độ chắc chắn 0..1."
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
        "t_ref": {"type": "number"},       # giây trong clip nơi quan sát thấy (0 nếu không rõ)
        "confidence": {"type": "number"},  # độ chắc chắn 0..1
    },
    "required": ["aspect", "text", "t_ref", "confidence"],
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
        "serve_variety": {  # qualitative serve-diversity read (no counting)
            "type": "object",
            "properties": {"notes": {"type": "string"}},
            "required": ["notes"],
        },
        "tactics": {  # qualitative tactical tendencies / patterns (no counting)
            "type": "object",
            "properties": {"notes": {"type": "string"}},
            "required": ["notes"],
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "identified", "confidence", "subject", "summary", "strengths",
        "weaknesses", "serve", "footwork", "posture", "serve_variety", "tactics",
        "recommendations",
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

# Clip focus (L8) → what the coach should concentrate on. Steers attention so a
# serve-practice clip isn't graded on footwork it never shows, and a match clip
# gets a tactical/decision read, not just posture. "" / "free" → no steer.
FOCUS_VALUES = ("serve_practice", "footwork_drill", "rally", "match", "free", "")

_FOCUS_VI = {
    "serve_practice": (
        "TRỌNG TÂM CLIP: GIAO BÓNG. Soi kỹ động tác tung bóng (độ cao, ổn định), điểm tiếp xúc, "
        "cổ tay tạo xoáy, độ thấp/ngắn của bóng, sự đa dạng & che giấu xoáy, điểm rơi. Các mảng "
        "khác (bộ chân, rally) ÍT liên quan ở clip này — chỉ nhận xét nếu thật sự nhìn thấy rõ."
    ),
    "footwork_drill": (
        "TRỌNG TÂM CLIP: BỘ CHÂN / DI CHUYỂN. Soi kỹ bước chân, trọng tâm, split-step, tốc độ & "
        "biên độ di chuyển, hồi vị sau mỗi cú, giữ thăng bằng. Giao bóng ít liên quan ở clip này."
    ),
    "rally": (
        "TRỌNG TÂM CLIP: CÁC PHA BÓNG QUA LẠI (rally). Soi độ ổn định, chọn cú đánh, luân chuyển "
        "thuận/trái tay, nhịp độ, khả năng duy trì bóng và chuyển từ thủ sang công."
    ),
    "match": (
        "TRỌNG TÂM CLIP: ĐIỂM TRONG TRẬN ĐẤU. Ngoài kỹ thuật, hãy đọc CHIẾN THUẬT: chọn điểm rơi, "
        "ý đồ ghi điểm, xử lý dưới áp lực, tâm lý thi đấu. Đánh giá cả quyết định, không chỉ động tác."
    ),
}


def _focus_block(focus: str) -> str:
    """Vietnamese 'what to focus on' line for the prompt (empty for free/unknown)."""
    return _FOCUS_VI.get(focus, "")


def _clamp01(v: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


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
             me_appearance: str = "", handed: str = "right",
             stroke_context: str = "", montage: bool = False, focus: str = "") -> dict[str, Any]:
    """Send reference images + frames + pose context to Ollama; return parsed JSON.
    When ``montage`` is set, the leading images are per-stroke montages (a swing
    read left→right) rather than evenly-spaced stills, and ``stroke_context`` adds
    the auto-detected stroke/tempo facts to the prompt."""
    refs = (reference_images_b64 or [])[:REF_MAX]
    if montage:
        intro = (
            f"Có {len(refs)} ảnh tham chiếu (nếu >0), rồi đến {len(images_b64)} ẢNH. "
            "Phần đầu là các ẢNH GHÉP — mỗi ảnh ghép là MỘT KHOẢNH KHẮC ĐÁNH BÓNG gồm nhiều khung "
            "hình xếp trái→phải theo thời gian (trước → lúc → sau khi tiếp xúc bóng); phần sau là "
            "vài khung toàn cảnh. Hãy phân tích kỹ thuật theo diễn tiến động tác trong mỗi ảnh ghép."
        )
    else:
        intro = (
            f"Có {len(refs)} ảnh tham chiếu (nếu >0) rồi đến {len(images_b64)} khung hình trích đều "
            f"từ một {_CLIP_TYPE_VI.get(clip_type, 'clip')} (theo thứ tự thời gian)."
        )
    context_block = f"Bối cảnh cú đánh (tự động phát hiện, có thể sai):\n{stroke_context}\n\n" if stroke_context else ""
    fb = _focus_block(focus)
    focus_block = f"{fb}\n\n" if fb else ""
    user_text = (
        f"{intro}\n\n"
        f"Thông tin nhận diện Thảo:\n{_identity_block(refs, me_side, me_appearance, handed)}\n\n"
        f"{focus_block}"
        f"{context_block}"
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


# ------------------------------------------------ self-critique (Pass C, S7)
# A general 8B VLM over-claims technique it can't actually see. Pass C re-shows it
# the SAME frames + pose numbers and its own draft findings, and asks it to judge,
# per finding, whether the claim is grounded in what's visible. Unsupported claims
# are dropped and shaky ones are downgraded BEFORE they become proposed traits —
# the human review gate then has a cleaner, more honest list to confirm.
SELF_CRITIQUE = True  # config knob: an extra VLM pass (slower, but more honest)

_CRITIQUE_SYSTEM_PROMPT = (
    "Bạn là một HLV bóng bàn khó tính ĐANG KIỂM TRA LẠI bản nháp nhận xét do một AI khác viết về "
    "học trò Nguyễn Bá Thảo. Bạn chỉ được dựa vào CHÍNH các ảnh (mỗi ảnh ghép = một cú đánh, xếp "
    "trái→phải theo thời gian) và số liệu pose kèm theo — ĐỪNG tin lời, chỉ tin thứ NHÌN THẤY. "
    "Với MỖI nhận xét (theo idx), đánh giá khắt khe mức độ có căn cứ:\n"
    "- supported='yes': nhìn rõ bằng chứng trong ảnh hoặc số liệu.\n"
    "- supported='partly': có thể đúng nhưng mờ/không chắc/khó thấy rõ.\n"
    "- supported='no': KHÔNG có căn cứ (suy diễn, nói chung chung, hoặc mâu thuẫn với ảnh).\n"
    "Khi phân vân hãy nghiêng về 'partly' hoặc 'no'. confidence = độ chắc 0..1 SAU khi kiểm tra. "
    "Trả về verdicts cho TỪNG idx. Chỉ trả JSON đúng schema, không thêm chữ nào."
)

_CRITIQUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idx": {"type": "integer"},
                    "supported": {"type": "string", "enum": ["yes", "partly", "no"]},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["idx", "supported", "confidence"],
            },
        }
    },
    "required": ["verdicts"],
}


def self_critique(images_b64: list[str], pose_text: str,
                  findings: list[dict[str, Any]], model: str, *,
                  stroke_context: str = "", montage: bool = False) -> dict[int, dict[str, Any]]:
    """Pass C — re-examine each draft finding against the same frames + pose and
    return a verdict per finding (keyed by ``idx``). ``findings`` is a flat list of
    ``{idx, polarity, aspect, text}``. Returns ``{idx: {supported, confidence}}``,
    or {} on any failure (caller then keeps every finding unchanged)."""
    if not findings:
        return {}
    lines = []
    for f in findings:
        pol = "điểm mạnh" if f.get("polarity") == "strength" else "điểm yếu"
        lines.append(f"  [{f['idx']}] ({pol} / {f.get('aspect', 'other')}) {f['text']}")
    ctx = f"Bối cảnh cú đánh:\n{stroke_context}\n\n" if stroke_context else ""
    kind = "ảnh ghép cú đánh" if montage else "khung hình"
    user_text = (
        f"{len(images_b64)} {kind} dưới đây là tư liệu để kiểm chứng (đúng tư liệu AI kia đã xem).\n\n"
        f"{ctx}"
        f"Số liệu pose đo được:\n{pose_text}\n\n"
        f"Các nhận xét cần kiểm tra:\n" + "\n".join(lines) + "\n\n"
        "Hãy chấm verdict cho TỪNG nhận xét theo idx. Trả JSON đúng schema."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _CRITIQUE_SYSTEM_PROMPT},
            {"role": "user", "content": user_text, "images": images_b64},
        ],
        "stream": False,
        "format": _CRITIQUE_SCHEMA,
        "options": {"temperature": 0.1, "num_ctx": VLM_NUM_CTX},
    }
    resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=900.0)
    resp.raise_for_status()
    content = resp.json().get("message", {}).get("content", "{}")
    data = json.loads(content)
    out: dict[int, dict[str, Any]] = {}
    for v in (data.get("verdicts", []) if isinstance(data, dict) else []):
        try:
            out[int(v["idx"])] = v
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _apply_self_critique(raw: dict[str, Any], images_b64: list[str], pose_text: str,
                         model: str, *, stroke_context: str = "",
                         montage: bool = False) -> dict[str, Any]:
    """Run Pass C over ``raw``'s strengths/weaknesses, then drop unsupported
    findings and downgrade shaky ones in place. Records a small ``critique``
    summary on ``raw`` for the UI. Best-effort — never raises (the analysis is
    still useful without the critique)."""
    flat: list[dict[str, Any]] = []
    for polarity, key in (("strength", "strengths"), ("weakness", "weaknesses")):
        for item in raw.get(key, []) or []:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            flat.append({"idx": len(flat), "polarity": polarity, "key": key,
                         "aspect": item.get("aspect", "other"), "text": text, "item": item})
    if not flat:
        return raw

    try:
        verdicts = self_critique(
            images_b64, pose_text,
            [{k: f[k] for k in ("idx", "polarity", "aspect", "text")} for f in flat],
            model, stroke_context=stroke_context, montage=montage,
        )
    except Exception as exc:  # pragma: no cover - network/parse guard
        print(f"[video_analysis] self-critique skipped: {exc}", flush=True)
        return raw
    if not verdicts:
        return raw

    kept: dict[str, list[Any]] = {"strengths": [], "weaknesses": []}
    dropped = downgraded = 0
    for f in flat:
        item, v = f["item"], verdicts.get(f["idx"])
        if v is None:  # model said nothing about this one → keep as-is
            kept[f["key"]].append(item)
            continue
        supported = str(v.get("supported", "partly")).lower()
        revised = _clamp01(v.get("confidence"))
        orig = _clamp01(item.get("confidence"))
        if supported == "no":
            dropped += 1
            continue
        if supported == "partly":
            # Shaky → take the most conservative confidence and cap it.
            cands = [c for c in (orig, revised, 0.6) if c is not None]
            item["confidence"] = round(min(cands), 2) if cands else 0.5
            downgraded += 1
        else:  # yes → trust the re-checked confidence
            item["confidence"] = revised if revised is not None else orig
        kept[f["key"]].append(item)

    raw["strengths"] = kept["strengths"]
    raw["weaknesses"] = kept["weaknesses"]
    raw["critique"] = {"reviewed": len(flat), "dropped": dropped, "downgraded": downgraded}
    print(f"[video_analysis] self-critique: reviewed={len(flat)} dropped={dropped} "
          f"downgraded={downgraded}", flush=True)
    return raw


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


_HAND_VI = {"forehand": "thuận tay (FH)", "backhand": "trái tay (BH)", "unknown": "chưa rõ"}


def _stroke_context_text(shown: list[dict[str, Any]], strokes: list[dict[str, Any]],
                         impacts: list[float]) -> str:
    """Vietnamese facts about the auto-detected strokes/tempo, for the VLM prompt.
    ``shown`` are the strokes whose montages are attached (in image order)."""
    lines = [f"- Tự động phát hiện {len(strokes)} cú đánh trong clip."]
    if len(impacts) >= 2:
        gaps = [impacts[i] - impacts[i - 1] for i in range(1, len(impacts))]
        avg = sum(gaps) / len(gaps)
        lines.append(f"- ~{len(impacts)} lần chạm bóng (âm thanh), nhịp trung bình {avg:.2f}s/lần.")
    elif impacts:
        lines.append(f"- {len(impacts)} lần chạm bóng (âm thanh).")
    lines.append(f"- {len(shown)} ảnh ghép dưới đây tương ứng các cú đánh sau (theo thứ tự):")
    for n, s in enumerate(shown, 1):
        lines.append(f"  • Ảnh ghép #{n}: cú lúc {s['t_contact']}s, loại (đoán): {_HAND_VI.get(s['hand'], s['hand'])}.")
    return "\n".join(lines)


def _impact_context_text(picks: list[float], impacts: list[float]) -> str:
    """Prompt facts for the impact-anchored path (pose strokes unavailable)."""
    lines = [f"- Tự động phát hiện ~{len(impacts)} lần chạm bóng (theo âm thanh)."]
    if len(impacts) >= 2:
        gaps = [impacts[i] - impacts[i - 1] for i in range(1, len(impacts))]
        lines.append(f"- Nhịp đánh trung bình {sum(gaps) / len(gaps):.2f}s/lần.")
    lines.append(f"- {len(picks)} ảnh ghép dưới đây là khoảnh khắc quanh lúc chạm bóng tại các thời "
                 f"điểm {', '.join(f'{t:.1f}s' for t in picks)} (trái→phải: trước → lúc → sau chạm). "
                 "Chưa tách được cú đánh từ tư thế (người chơi ở xa), hãy phân tích dựa trên các ảnh ghép này.")
    return "\n".join(lines)


def analyze_file(path: str, clip_type: str, model: str | None = None, *,
                 me_side: str = "", me_appearance: str = "", handed: str = "right",
                 reference_images_b64: list[str] | None = None, focus: str = "") -> dict[str, Any]:
    """Full pipeline for one clip. Motion-aware (S1/S2/S4/S6): sample once with
    timestamps, detect ball-contact impacts (audio) + strokes (pose), and feed the
    VLM per-stroke montages + stroke context. Falls back to evenly-spaced stills
    when no strokes are found, so behaviour is never worse than before. Returns
    {model, frames_sampled, pose, raw, summary, ref_crops_b64, strokes, impacts,
    metrics}."""
    model = model or DEFAULT_VLM_MODEL
    # Sample by duration so a long clip isn't reduced to a handful of stills.
    try:
        duration = (probe(path) or {}).get("duration_sec") or 0.0
    except Exception:
        duration = 0.0
    n_sample = (max(POSE_MIN_FRAMES, min(POSE_CAP_FRAMES, int(duration * SAMPLE_TARGET_FPS)))
                if duration else POSE_MAX_FRAMES)
    track_ts = sample_timestamped(path, n_sample)
    if not track_ts:
        raise RuntimeError("Không đọc được khung hình nào từ clip (file hỏng hoặc định dạng lạ).")
    eff_fps = round(len(track_ts) / duration, 2) if duration else None

    # Pose/strokes lock onto the user only when we know their side; else best-effort.
    cropped = me_side in _SIDE_VI
    player_ts = [(t, crop_side(f, me_side)) for t, f in track_ts] if cropped else track_ts
    player_frames = [f for _, f in player_ts]

    # One MediaPipe pass → per-frame records (wrist trajectory + biomechanics).
    records, _detected, pose_ok, pose_reason = analyze_pose(player_ts, handed)

    # Motion stages — best-effort (empty on failure → graceful fallback).
    # Cross-validate audio against player-region motion to drop neighbour-table
    # 'tock' cross-talk (noisy multi-table halls), then use the kept impacts
    # everywhere (stroke-contact snapping + the impact-anchored fallback).
    impacts_raw = detect_impacts(path)
    impacts = corroborate_impacts(impacts_raw, motion_energy(player_ts))
    series = [r for r in records if r["wvis"] > 0.3]
    strokes = segment_strokes(series, impacts, handed=handed)

    # Measure biomechanics DURING the strokes (not idle standing) when possible.
    if pose_ok:
        intervals = [(s["t_start"], s["t_end"]) for s in strokes]
        pose = aggregate_pose(records, len(player_ts), intervals)
        pose["dynamics"] = stroke_dynamics(strokes)
        scope = "các cú đánh" if pose.get("measured_on") == "strokes" else "toàn clip"
        where = _SIDE_VI[me_side] if cropped else "người nổi bật trong khung"
        pose["note"] = f"đo trên {scope}, vùng {where}"
    else:
        pose = {"available": False, "reason": pose_reason}

    # Build montages, preferring pose-segmented strokes; if pose failed but we have
    # audio impacts, anchor montages on the contact times instead (robust when the
    # player is far/small and pose is weak). Fall back to even stills otherwise.
    ctx = [_to_jpeg_b64(player_frames[i])
           for i in _even_indices(len(player_frames), VLM_CONTEXT_FRAMES)]
    montages: list[str] = []
    stroke_context = ""
    motion_path = "stills"
    shown: list[dict[str, Any]] = []
    if strokes:
        # Spread the montages ACROSS the clip (even over time) rather than taking the
        # few fastest swings, so a long clip is sampled broadly, not in one cluster.
        ordered = sorted(strokes, key=lambda s: s["t_contact"])
        shown = [ordered[i] for i in _even_indices(len(ordered), VLM_MAX_STROKES)]
        montages = [m for m in (stroke_montage_b64(player_ts, s) for s in shown) if m]
        if montages:
            motion_path = "pose"
            stroke_context = _stroke_context_text(shown, strokes, impacts)
    elif impacts:
        picks = [impacts[i] for i in _even_indices(len(impacts), VLM_MAX_STROKES)]
        for t in picks:
            win = decode_at_times(path, [t - 0.12, t, t + 0.12])
            frames = [crop_side(f, me_side) if cropped else f for _, f in win]
            m = montage_strip(frames)
            if m:
                montages.append(m)
        if montages:
            motion_path = "impact"
            stroke_context = _impact_context_text(picks, impacts)

    if montages:
        images_b64 = montages + ctx
        montage = True
    else:
        # Even-stills fallback (original behaviour).
        images_b64 = [_to_jpeg_b64(player_frames[i])
                      for i in _even_indices(len(player_frames), VLM_MAX_FRAMES)]
        montage = False

    if not images_b64:
        raise RuntimeError("Không tạo được khung hình để phân tích.")

    # Visible signal (backend console) of which path the analysis took.
    print(f"[video_analysis] motion: path={motion_path} sampled={len(track_ts)} "
          f"(~{eff_fps}fps, {round(duration,1)}s) strokes={len(strokes)} "
          f"impacts={len(impacts_raw)}->{len(impacts)} images={len(images_b64)} "
          f"montage={montage}", flush=True)

    pose_text = pose_to_text(pose)
    raw = call_vlm(
        images_b64, pose_text, clip_type, model,
        reference_images_b64=reference_images_b64, me_side=me_side,
        me_appearance=me_appearance, handed=handed,
        stroke_context=stroke_context, montage=montage, focus=focus,
    )
    # Pass C: re-check the draft findings against the same frames; drop unsupported
    # claims and downgrade shaky ones before they reach the human review gate.
    if SELF_CRITIQUE:
        raw = _apply_self_critique(raw, images_b64, pose_text, model,
                                   stroke_context=stroke_context, montage=montage)
    # Annotated evidence thumbnails (NC4a): one per shown stroke (pose path only —
    # needs body geometry). A finding's t_ref is later matched to the nearest one.
    evidence: list[dict[str, Any]] = []
    if motion_path == "pose":
        for s in shown:
            frame = frame_at_time(player_ts, s["t_contact"])
            thumb = annotate_pose_frame(frame, handed, hand=s["hand"], t=s["t_contact"])
            evidence.append({"stroke_idx": s["idx"], "t": round(s["t_contact"], 3),
                             "hand": s["hand"], "thumb_b64": thumb})

    # Ball + table tracking (Phase 4 / NC1) — best-effort over the full frames
    # (the ball can be anywhere, not just the player's side). Never blocks.
    table_frame = track_ts[len(track_ts) // 2][1] if track_ts else None
    ball = ball_tracker.analyze_ball(track_ts, table_frame=table_frame)
    print(f"[video_analysis] ball: method={ball.get('method')} "
          f"points={ball.get('n_points')} conf={ball.get('mean_conf')} "
          f"table={'yes' if ball.get('table') else 'no'} available={ball.get('available')}",
          flush=True)

    # Auto-build references only from labelled clips (we trust the side here).
    ref_crops_b64 = subject_crops([f for _, f in track_ts], me_side) if cropped else []
    return {
        "model": model,
        "frames_sampled": len(images_b64),
        "pose": pose,
        "raw": raw,
        "summary": raw.get("summary", ""),
        "ref_crops_b64": ref_crops_b64,
        "strokes": strokes,
        "impacts": impacts,
        "metrics": pose_to_metrics(pose),
        "evidence": evidence,
        "ball": ball,
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
