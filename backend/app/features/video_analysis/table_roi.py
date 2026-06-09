"""Foreground table-ROI detection via a trained YOLOv8-seg model.

The model (`settings.TABLE_ROI_MODEL_PATH`, default `data/models/roi_seg.pt`) was
fine-tuned by the user in the `video_studio_v3` project on many hand-labelled table
examples — it segments the *foreground* table (the one being played on) far more
reliably than classical colour segmentation, which trips on green floors / multiple
tables. This module is a self-contained port of that project's YOLO ROI tier:
lazy-loaded, optional (returns None if the model file or ultralytics is absent),
and dependency-free at import time.

Output: 4 normalised corners ordered clockwise-from-top-left + confidence + the
mask's area fraction, ready to feed a homography. Credit: algorithm/weights from
video_studio_v3 `backend/roi_yolo.py`.
"""
from __future__ import annotations

import logging
import threading

import numpy as np

from app.core.settings import TABLE_ROI_MODEL_PATH

_logger = logging.getLogger(__name__)
_model_cache: object | None | bool = None  # None=untried, False=unavailable, else model
_model_lock = threading.Lock()

_YOLO_MIN_CONF = 0.55
_YOLO_IMGSZ = 640
# Mask-area sanity: below → partial/irrelevant blob; above → fired on a wall +
# multiple tables. The foreground table is a modest slice of a wide frame.
_MIN_AREA_FRAC = 0.008
_MAX_AREA_FRAC = 0.45


def _load_model():
    """Load the YOLO model once (or None if unavailable). One stat() + import
    attempt per process; failures are cached so we never retry on the hot path."""
    global _model_cache
    if _model_cache is False:
        return None
    if _model_cache is not None:
        return _model_cache
    with _model_lock:
        if _model_cache is not None:
            return None if _model_cache is False else _model_cache
        if not TABLE_ROI_MODEL_PATH.is_file():
            _logger.info("table ROI model absent (%s) — classical fallback", TABLE_ROI_MODEL_PATH)
            _model_cache = False
            return None
        try:
            from ultralytics import YOLO

            model = YOLO(str(TABLE_ROI_MODEL_PATH))
            model.predict(np.zeros((_YOLO_IMGSZ, _YOLO_IMGSZ, 3), dtype=np.uint8),
                          imgsz=_YOLO_IMGSZ, verbose=False)  # warm CUDA/JIT once
            _model_cache = model
            print(f"[video_analysis] table ROI: YOLOv8-seg loaded ({TABLE_ROI_MODEL_PATH.name})",
                  flush=True)
            return model
        except Exception as exc:  # pragma: no cover - optional dep / load guard
            _logger.warning("table ROI model load failed: %s — classical fallback", exc)
            _model_cache = False
            return None


def _polygon_to_quad(polygon_xy: np.ndarray):
    """Reduce a segmentation polygon to a 4-corner quad: max-area approxPolyDP at
    increasing epsilon, else minAreaRect (always 4 distinct, non-degenerate)."""
    import cv2

    if polygon_xy is None or len(polygon_xy) < 4:
        return None
    pts = polygon_xy.astype(np.float32).reshape(-1, 1, 2)
    hull = cv2.convexHull(pts)
    peri = cv2.arcLength(hull, True)
    hp = hull.reshape(-1, 2)
    bbox_diag = float(np.hypot(hp[:, 0].max() - hp[:, 0].min(), hp[:, 1].max() - hp[:, 1].min()))
    min_edge = 0.01 * bbox_diag

    best_quad, best_area = None, -1.0
    for eps in (0.015, 0.02, 0.025, 0.03, 0.04, 0.06, 0.08, 0.10):
        approx = cv2.approxPolyDP(hull, eps * peri, True)
        if len(approx) != 4:
            continue
        quad = approx.reshape(-1, 2).astype(np.float32)
        if min(float(np.linalg.norm(quad[i] - quad[(i + 1) % 4])) for i in range(4)) < min_edge:
            continue
        area = float(abs(cv2.contourArea(quad)))
        if area > best_area:
            best_area, best_quad = area, quad
    if best_quad is not None:
        return best_quad
    return cv2.boxPoints(cv2.minAreaRect(hull)).astype(np.float32)


def _order_cw_from_tl(pts):
    """Order 4 points clockwise starting from the top-left (smallest y, then x)."""
    arr = np.asarray(pts, dtype=np.float64)
    cx, cy = arr[:, 0].mean(), arr[:, 1].mean()
    order = np.argsort(np.arctan2(arr[:, 1] - cy, arr[:, 0] - cx))
    sp = arr[order]
    ys, xs = sp[:, 1], sp[:, 0]
    tied = np.where(ys <= ys.min() + 1e-9)[0]
    tl = int(tied[np.argmin(xs[tied])]) if len(tied) > 1 else int(tied[0])
    sp = np.roll(sp, -tl, axis=0)
    return [[float(p[0]), float(p[1])] for p in sp]


def detect_table_quad(img_bgr) -> dict | None:
    """Run the YOLOv8-seg model and return the foreground table as a quad:
    ``{corners: [[x,y]*4] (normalised, CW from TL), confidence, area_frac}``.
    Returns None when the model/ultralytics is unavailable, nothing fires above
    the confidence threshold, or the mask fails area sanity."""
    import cv2

    model = _load_model()
    if model is None:
        return None
    results = model.predict(img_bgr, imgsz=_YOLO_IMGSZ, conf=_YOLO_MIN_CONF, verbose=False)
    if not results:
        return None
    r0 = results[0]
    if r0.masks is None or r0.boxes is None or len(r0.boxes) == 0:
        return None

    h, w = img_bgr.shape[:2]
    confs = r0.boxes.conf.cpu().numpy()
    best = int(np.argmax(confs))

    poly = None
    if getattr(r0.masks, "xy", None) is not None and best < len(r0.masks.xy):
        poly = np.asarray(r0.masks.xy[best], dtype=np.float32)
    if poly is None:
        mask = r0.masks.data[best].cpu().numpy().astype(np.uint8) * 255
        if mask.shape != (h, w):
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        poly = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)

    quad_px = _polygon_to_quad(poly)
    if quad_px is None:
        return None

    # Shoelace area of the raw polygon (px) → area fraction sanity.
    n = len(poly)
    area_px = abs(sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
                      for i in range(n))) / 2.0
    area_frac = float(area_px / max(w * h, 1.0))
    if not (_MIN_AREA_FRAC <= area_frac <= _MAX_AREA_FRAC):
        return None

    corners = _order_cw_from_tl(
        [[max(0.0, min(1.0, p[0] / w)), max(0.0, min(1.0, p[1] / h))] for p in quad_px]
    )
    return {"corners": corners, "confidence": float(confs[best]), "area_frac": round(area_frac, 4)}
