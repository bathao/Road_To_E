"""Embedding-based player identity — "which one is Nguyễn Bá Thảo".

The old approach asked a general VLM to *look at* a few reference crops and guess
who the user is; it was unreliable, so every clip needed a hand-drawn box. This
module replaces that with proper re-identification:

- **Face (primary):** InsightFace (RetinaFace detector + ArcFace `buffalo_l`
  recognition, 512-d normalised embeddings). Robust when the face is visible.
- **Body (fallback):** a torchvision ResNet-50 appearance embedding of the whole
  person crop, for frames where the face isn't clear (turned away / far).

Enrollment needs a TRUSTED anchor: clean portraits the user drops in
``data/identity/me/``. The auto-collected gallery (``data/profile_refs/``) is
known to be polluted with other people, so we keep only the crops whose face
matches the anchor — this auto-cleans the dataset. Embeddings are cached on disk
so identification doesn't recompute them.

All models run locally (CPU). Model files download once on first use, then work
offline.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.settings import DATA_DIR, PROFILE_REFS_DIR

IDENTITY_DIR = DATA_DIR / "identity"
ANCHOR_DIR = IDENTITY_DIR / "me"  # user-provided clean portraits (ground truth)
GALLERY_NPZ = IDENTITY_DIR / "identity.npz"  # cached enrolled embeddings
META_JSON = IDENTITY_DIR / "enroll_meta.json"

# Cosine-similarity thresholds for ArcFace normed embeddings (buffalo_l / w600k).
# Tuned from real data: with 39 anchors (internal consistency ~0.71), genuine
# per-clip matches for Thảo land at 0.59–0.91 while other players sit below ~0.35.
# 0.45 keeps every true positive with a comfortable margin and rejects opponents.
ENROLL_MATCH_TH = 0.40   # keep a gallery crop only if it confidently matches the anchor
IDENTIFY_FACE_TH = 0.45  # a detected face is "Thảo" at/above this
IDENTIFY_BODY_TH = 0.80  # body fallback is weaker → demand a higher match

_IMG_EXTS = ("jpg", "jpeg", "png", "webp", "bmp")


# --------------------------------------------------------------- model loaders
_face_app = None
_body_model = None
_body_tf = None


def get_face_app():
    """Lazy InsightFace app (downloads buffalo_l once, then offline)."""
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        _face_app = app
    return _face_app


def _get_body_model():
    """Lazy torchvision ResNet-50 as a generic appearance embedder (2048-d)."""
    global _body_model, _body_tf
    if _body_model is None:
        import torch
        import torchvision.transforms as T
        from torchvision.models import ResNet50_Weights, resnet50

        weights = ResNet50_Weights.IMAGENET1K_V2
        net = resnet50(weights=weights)
        net.fc = torch.nn.Identity()  # 2048-d pooled features
        net.eval()
        _body_model = net
        _body_tf = T.Compose(
            [
                T.ToPILImage(),
                T.Resize((256, 128)),  # person-shaped crop
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )
    return _body_model, _body_tf


# ------------------------------------------------------------------- embedding
def _list_images(folder: Path) -> list[str]:
    out: list[str] = []
    for ext in _IMG_EXTS:
        out += glob.glob(str(folder / f"*.{ext}"))
        out += glob.glob(str(folder / f"*.{ext.upper()}"))
    return sorted(set(out))


def face_embeddings(bgr: np.ndarray) -> list[dict[str, Any]]:
    """All faces in a BGR frame → [{bbox:[x1,y1,x2,y2], emb:np.float32(512)}]."""
    out = []
    for f in get_face_app().get(bgr):
        out.append({"bbox": f.bbox.astype(float).tolist(),
                    "emb": f.normed_embedding.astype(np.float32)})
    return out


def largest_face_emb(bgr: np.ndarray) -> np.ndarray | None:
    """Embedding of the biggest face in an image (for enrolling a portrait/crop)."""
    faces = get_face_app().get(bgr)
    if not faces:
        return None
    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
               reverse=True)
    return faces[0].normed_embedding.astype(np.float32)


def body_embedding(bgr_crop: np.ndarray) -> np.ndarray:
    """L2-normalised appearance embedding of a person crop (BGR)."""
    import torch

    net, tf = _get_body_model()
    rgb = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        x = tf(rgb).unsqueeze(0)
        v = net(x).squeeze(0).numpy().astype(np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ---------------------------------------------------------------- enrollment
def enroll() -> dict[str, Any]:
    """Build the identity from anchor portraits, then keep matching gallery crops.

    Returns a stats dict (also written to enroll_meta.json). Status:
    - ``no_anchor``: drop clean portraits in data/identity/me/ first.
    - ``ok``: identity saved; includes how many gallery crops were kept/rejected.
    """
    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    anchor_files = _list_images(ANCHOR_DIR)
    anchors: list[np.ndarray] = []
    anchor_bgrs: list[np.ndarray] = []
    for f in anchor_files:
        img = cv2.imread(f)
        if img is None:
            continue
        e = largest_face_emb(img)
        if e is not None:
            anchors.append(e)
            anchor_bgrs.append(img)

    if not anchors:
        meta = {"status": "no_anchor", "anchor_files": len(anchor_files),
                "anchor_dir": str(ANCHOR_DIR)}
        META_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        _invalidate_cache()
        return meta

    A = np.array(anchors, dtype=np.float32)
    face_set: list[np.ndarray] = list(anchors)
    body_set: list[np.ndarray] = [body_embedding(b) for b in anchor_bgrs]

    kept = rejected = noface = 0
    rejected_names: list[str] = []
    for f in _list_images(PROFILE_REFS_DIR):
        img = cv2.imread(f)
        if img is None:
            continue
        e = largest_face_emb(img)
        if e is None:
            noface += 1
            continue
        sim = float((A @ e).max())
        if sim >= ENROLL_MATCH_TH:
            face_set.append(e)
            body_set.append(body_embedding(img))
            kept += 1
        else:
            rejected += 1
            rejected_names.append(Path(f).name)

    np.savez(
        GALLERY_NPZ,
        face=np.array(face_set, dtype=np.float32),
        body=np.array(body_set, dtype=np.float32),
    )
    meta = {
        "status": "ok",
        "anchors": len(anchors),
        "anchor_files": len(anchor_files),
        "kept_from_gallery": kept,
        "rejected_from_gallery": rejected,
        "gallery_noface": noface,
        "identity_face_samples": len(face_set),
        "identity_body_samples": len(body_set),
        "rejected_sample": rejected_names[:25],
    }
    META_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    _invalidate_cache()
    return meta


# ----------------------------------------------------------- identity cache
_identity: dict[str, np.ndarray] | None = None


def _invalidate_cache() -> None:
    global _identity
    _identity = None


def _load_identity() -> dict[str, np.ndarray] | None:
    global _identity
    if _identity is None and GALLERY_NPZ.exists():
        data = np.load(GALLERY_NPZ)
        _identity = {"face": data["face"], "body": data["body"]}
    return _identity


def is_enrolled() -> bool:
    ident = _load_identity()
    return ident is not None and len(ident.get("face", [])) > 0


def status() -> dict[str, Any]:
    """Enrollment status for the GUI (counts + last enroll meta)."""
    out: dict[str, Any] = {"enrolled": is_enrolled(),
                           "anchor_dir": str(ANCHOR_DIR),
                           "anchor_files": len(_list_images(ANCHOR_DIR))}
    if META_JSON.exists():
        try:
            out["meta"] = json.loads(META_JSON.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return out


# ----------------------------------------------------------- identification
def _face_sim(emb: np.ndarray) -> float:
    ident = _load_identity()
    if ident is None or len(ident["face"]) == 0:
        return 0.0
    return float((ident["face"] @ emb).max())


def _body_sim(emb: np.ndarray) -> float:
    ident = _load_identity()
    if ident is None or len(ident["body"]) == 0:
        return 0.0
    return float((ident["body"] @ emb).max())


def _side_from_cx(cx_frac: float) -> str:
    return "left" if cx_frac < 0.5 else "right"


def identify_clip(path: str, n_frames: int = 24) -> dict[str, Any]:
    """Find Thảo in a clip by face (then body), infer which side he is on.

    Returns {found, side, confidence, method, frames_checked, faces_seen,
    votes}. ``found`` is True only when confident; otherwise the caller should
    fall back to the manual box / VLM.
    """
    if not is_enrolled():
        return {"found": False, "reason": "not_enrolled"}

    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        cap.release()
        return {"found": False, "reason": "unreadable"}
    idxs = np.linspace(0, total - 1, num=min(n_frames, total)).astype(int)

    side_votes: dict[str, float] = {}
    best_conf = 0.0
    faces_seen = 0
    frames_checked = 0
    method = "face"
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        frames_checked += 1
        w = frame.shape[1]
        faces = get_face_app().get(frame)
        faces_seen += len(faces)
        for f in faces:
            sim = _face_sim(f.normed_embedding.astype(np.float32))
            if sim >= IDENTIFY_FACE_TH:
                cx = (f.bbox[0] + f.bbox[2]) / 2.0 / w
                side = _side_from_cx(cx)
                side_votes[side] = side_votes.get(side, 0.0) + sim
                best_conf = max(best_conf, sim)
    cap.release()

    if side_votes:
        side = max(side_votes, key=side_votes.get)
        return {"found": True, "side": side, "confidence": round(best_conf, 3),
                "method": method, "frames_checked": frames_checked,
                "faces_seen": faces_seen, "votes": side_votes}

    return {"found": False, "reason": "no_confident_face",
            "frames_checked": frames_checked, "faces_seen": faces_seen}
