"""Ball + table tracking (Phase 4 / NC1) — **best-effort, never a hard gate**.

Table tennis placement reads need two things: where the ball is (image plane) and
where the table plane sits (to turn an image point into a table coordinate / zone).
Both are hard on a single uncalibrated phone camera, so everything here degrades
gracefully: any failure → ``{"available": False, ...}`` and the rest of the
analysis is unaffected (mirrors how pose degrades).

Two detector tiers, picked automatically:
- **TrackNet (ONNX)** — the real tool, used only if ``BALL_MODEL_PATH`` exists AND
  ``onnxruntime`` imports. A 40 mm ball at speed blurs to a streak on 30 fps phone
  footage, which classical detectors handle badly; a trained CNN is what actually
  works. Optional, pluggable — we never bundle or require it.
- **Classical motion blob** — the fallback: frame-difference + small round bright
  candidates. Brittle in busy halls, so it is confidence-gated hard and readily
  reports "not trackable" rather than inventing a trajectory.

Honest limits baked in: a single uncalibrated camera gives **placement zones**
(via table homography), NOT absolute speed/spin — we never claim those. Sparse
frame sampling caps trajectory fidelity. Low-confidence clips skip ball metrics.
"""
from __future__ import annotations

import math
from typing import Any

from app.core.settings import BALL_MODEL_PATH

# Working resolution for classical detection (speed + scale-stable thresholds).
_WORK_W = 640
# A ball blob at _WORK_W is small; bound its area to reject big moving bodies.
_BALL_AREA_MIN = 3.0
_BALL_AREA_MAX = 350.0
_BALL_CIRC_MIN = 0.55          # 4*pi*area/perimeter^2; 1.0 = perfect circle
_MIN_POINTS = 5                # fewer confident points than this → not usable
_MIN_MEAN_CONF = 0.35          # mean confidence gate for "available"

_onnx_session_cache: list = []  # [session] or [None]; one-shot lazily


# --------------------------------------------------------------- ONNX (tier 1)
def _load_session():
    """Load the TrackNet ONNX session once (or None if unavailable). Cached so we
    don't probe the disk / import onnxruntime on every clip."""
    if _onnx_session_cache:
        return _onnx_session_cache[0]
    session = None
    try:
        if BALL_MODEL_PATH.is_file():
            import onnxruntime as ort  # optional dependency

            providers = ort.get_available_providers()
            # Prefer CUDA when present (RTX), else CPU — never fail on provider.
            order = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in providers]
            session = ort.InferenceSession(str(BALL_MODEL_PATH), providers=order or None)
            print(f"[video_analysis] ball: TrackNet ONNX loaded ({order or 'default'})", flush=True)
    except Exception as exc:  # pragma: no cover - optional path
        print(f"[video_analysis] ball: ONNX unavailable, classical fallback ({exc})", flush=True)
        session = None
    _onnx_session_cache.append(session)
    return session


def _track_onnx(session, frames_ts: list[tuple[float, Any]]) -> list[dict[str, Any]]:
    """Run a TrackNet-style heatmap model over consecutive frame triplets and take
    the heatmap argmax as the ball position. Generic/defensive: model variants
    differ, so any shape mismatch falls through to [] (→ classical fallback)."""
    import cv2
    import numpy as np

    inp = session.get_inputs()[0]
    shape = inp.shape  # e.g. [1, 9, H, W] for 3 stacked RGB frames
    try:
        _, c, h, w = shape
        h, w = int(h), int(w)
        n_stack = int(c) // 3
    except (ValueError, TypeError):
        return []
    if n_stack < 1:
        return []

    out: list[dict[str, Any]] = []
    buf: list[Any] = []
    for t, frame in frames_ts:
        small = cv2.resize(frame, (w, h)).astype(np.float32) / 255.0
        buf.append(small.transpose(2, 0, 1))  # CHW
        if len(buf) < n_stack:
            continue
        stack = np.concatenate(buf[-n_stack:], axis=0)[None, ...]  # (1, 3*n, H, W)
        try:
            heat = session.run(None, {inp.name: stack})[0]
        except Exception:
            return out
        hm = np.asarray(heat).reshape(-1)
        idx = int(hm.argmax())
        conf = float(hm[idx])
        # Map flat index back to (y, x) on the heatmap grid.
        hy, hx = divmod(idx, w)
        if conf <= 0:
            continue
        out.append({"t": round(t, 3), "x": round(hx / w, 4), "y": round(hy / h, 4),
                    "conf": round(min(1.0, conf), 3)})
    return out


# ----------------------------------------------------------- classical (tier 2)
def _track_classical(frames_ts: list[tuple[float, Any]]) -> list[dict[str, Any]]:
    """Frame-difference + small round bright blob per frame. Fallback only —
    noisy, confidence-gated downstream."""
    import cv2
    import numpy as np

    out: list[dict[str, Any]] = []
    prev = None
    for t, frame in frames_ts:
        h0, w0 = frame.shape[:2]
        scale = _WORK_W / max(1, w0)
        g = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        g = cv2.resize(g, (int(w0 * scale), int(h0 * scale)))
        if prev is not None:
            diff = cv2.absdiff(g, prev)
            _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best, best_score = None, 0.0
            for c in cnts:
                area = cv2.contourArea(c)
                if not (_BALL_AREA_MIN <= area <= _BALL_AREA_MAX):
                    continue
                per = cv2.arcLength(c, True) or 1e-6
                circ = 4 * math.pi * area / (per * per)
                if circ < _BALL_CIRC_MIN:
                    continue
                (cx, cy), _ = cv2.minEnclosingCircle(c)
                bright = float(g[min(g.shape[0] - 1, int(cy)), min(g.shape[1] - 1, int(cx))]) / 255.0
                score = circ * (0.5 + 0.5 * bright)  # round + bright ball-ish
                if score > best_score:
                    best, best_score = (cx, cy), score
            if best is not None:
                gw, gh = g.shape[1], g.shape[0]
                # classical confidence is intentionally capped — it is a guess.
                out.append({"t": round(t, 3), "x": round(best[0] / gw, 4),
                            "y": round(best[1] / gh, 4),
                            "conf": round(min(0.6, best_score), 3)})
        prev = g
    return out


# ------------------------------------------------------------- table homography
def _order_corners(pts):
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    import numpy as np

    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]],
                    dtype="float32")


def detect_table(frame_rgb) -> dict[str, Any] | None:
    """Find the table as the largest blue/green quadrilateral and compute a
    homography to a canonical unit rectangle (x = left↔right across the width,
    y = near↔far along the length). Best-effort: None if no convincing quad."""
    import cv2
    import numpy as np

    hsv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2HSV)
    # Typical table colours: blue (~100-130 H) or green (~40-85 H), OpenCV H in 0..179.
    blue = cv2.inRange(hsv, (90, 60, 40), (135, 255, 255))
    green = cv2.inRange(hsv, (35, 50, 40), (90, 255, 255))
    mask = blue if int(blue.sum()) >= int(green.sum()) else green
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    h, w = frame_rgb.shape[:2]
    frame_area = float(w * h)
    big = max(cnts, key=cv2.contourArea)
    area_frac = cv2.contourArea(big) / frame_area
    if area_frac < 0.06:  # table should be a sizeable chunk of the frame
        return None
    peri = cv2.arcLength(big, True)
    approx = cv2.approxPolyDP(big, 0.02 * peri, True)
    if len(approx) == 4:
        quad = approx.reshape(-1, 2)
    else:
        # Players/net break the table contour into a non-quad. Fall back to the
        # minimum-area rectangle: a coarse but usable plane for 3×3 placement zones.
        quad = cv2.boxPoints(cv2.minAreaRect(big))
    corners = _order_corners(quad)
    dst = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype="float32")
    try:
        H = cv2.getPerspectiveTransform(corners, dst)
    except cv2.error:
        return None
    return {"corners": corners.tolist(), "H": H.tolist(),
            "area_frac": round(area_frac, 3),
            "color": "blue" if mask is blue else "green"}


def _to_table_coords(points: list[dict[str, Any]], frame_w: int, frame_h: int,
                     H) -> list[dict[str, Any]]:
    """Map normalised image points through the homography to table coords."""
    import cv2
    import numpy as np

    if not points:
        return []
    src = np.array([[[p["x"] * frame_w, p["y"] * frame_h]] for p in points], dtype="float32")
    dst = cv2.perspectiveTransform(src, np.array(H, dtype="float32")).reshape(-1, 2)
    out = []
    for p, (tx, ty) in zip(points, dst):
        out.append({**p, "tx": round(float(tx), 4), "ty": round(float(ty), 4)})
    return out


_ZONE_X = ["trái", "giữa", "phải"]
_ZONE_Y = ["gần lưới", "giữa bàn", "cuối bàn"]


def placement_zones(table_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bucket on-table points into a 3×3 grid and count hits per zone. Only points
    that landed within the table rectangle (0..1 both axes) count."""
    grid: dict[tuple[int, int], int] = {}
    for p in table_points:
        tx, ty = p.get("tx"), p.get("ty")
        if tx is None or ty is None or not (0 <= tx <= 1 and 0 <= ty <= 1):
            continue
        gx = min(2, int(tx * 3))
        gy = min(2, int(ty * 3))
        grid[(gx, gy)] = grid.get((gx, gy), 0) + 1
    out = [{"zone": f"{_ZONE_Y[gy]} · {_ZONE_X[gx]}", "gx": gx, "gy": gy, "count": n}
           for (gx, gy), n in grid.items()]
    return sorted(out, key=lambda z: z["count"], reverse=True)


# ----------------------------------------------------------------- orchestration
def analyze_ball(frames_ts: list[tuple[float, Any]],
                 table_frame=None) -> dict[str, Any]:
    """Best-effort ball + table read over the sampled frames. Returns a dict that
    is always safe to persist/serialise; ``available`` says whether anything
    trustworthy was found. Never raises."""
    base = {"available": False, "method": "none", "points": [], "table": None,
            "zones": [], "n_points": 0, "mean_conf": 0.0,
            "note": "Không bám được bóng đáng tin (clip xa/mờ hoặc lấy mẫu thưa)."}
    if not frames_ts:
        return base
    try:
        session = _load_session()
        method = "tracknet" if session is not None else "classical"
        points = _track_onnx(session, frames_ts) if session is not None else []
        if not points:  # ONNX absent or produced nothing → classical fallback
            points = _track_classical(frames_ts)
            method = "classical"

        confs = [p["conf"] for p in points]
        mean_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
        usable = len(points) >= _MIN_POINTS and mean_conf >= _MIN_MEAN_CONF

        table = detect_table(table_frame) if table_frame is not None else None
        zones: list[dict[str, Any]] = []
        if usable and table:
            h, w = (table_frame.shape[:2] if table_frame is not None
                    else frames_ts[0][1].shape[:2])
            points = _to_table_coords(points, w, h, table["H"])
            zones = placement_zones(points)

        # Honesty gate: the classical detector is noisy, so on its own it must NOT
        # claim a result — it only counts when a table homography turns its points
        # into actual on-table placement zones. A trained TrackNet trajectory is
        # trusted on its own (zones still need the table).
        available = (method == "tracknet" and usable) or bool(zones)
        if not available:
            base["method"] = method
            base["n_points"] = len(points)
            base["mean_conf"] = mean_conf
            base["table"] = table
            if method == "classical" and usable and not table:
                base["note"] = ("Có tín hiệu chuyển động nhưng chưa dựng được mặt bàn để xác "
                                "định điểm rơi — bỏ qua (cần model TrackNet hoặc clip rõ mặt bàn).")
            return base

        note = ("Bám bóng bằng " + ("mô hình TrackNet" if method == "tracknet"
                else "phương pháp chuyển động (best-effort, có thể nhiễu)") + ".")
        if not table:
            note += " Chưa dựng được mặt bàn nên chưa suy ra vùng điểm rơi."
        elif not zones:
            note += " Bóng không rơi rõ trong khung bàn."
        return {"available": True, "method": method, "points": points, "table": table,
                "zones": zones, "n_points": len(points), "mean_conf": mean_conf,
                "note": note}
    except Exception as exc:  # pragma: no cover - blanket best-effort guard
        print(f"[video_analysis] ball: skipped ({exc})", flush=True)
        return base
