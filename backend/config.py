from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "face_index.sqlite3"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"}

ENGINE_NAME = "InsightFace buffalo_l"
REQUESTED_PROVIDERS = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
DEFAULT_MODEL = "buffalo_l"
DEFAULT_MATCH_THRESHOLD = 0.42
DEFAULT_FACE_RECONCILE_THRESHOLD = 0.85
DEFAULT_FACE_BOX_IOU_THRESHOLD = 0.7

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")


def model_name() -> str:
    return os.environ.get("INSIGHTFACE_MODEL", DEFAULT_MODEL)


def match_threshold() -> float:
    return float(os.environ.get("FACE_MATCH_THRESHOLD", str(DEFAULT_MATCH_THRESHOLD)))


def face_reconcile_threshold() -> float:
    return float(os.environ.get("FACE_RECONCILE_THRESHOLD", str(DEFAULT_FACE_RECONCILE_THRESHOLD)))


def face_box_iou_threshold() -> float:
    return float(os.environ.get("FACE_BOX_IOU_THRESHOLD", str(DEFAULT_FACE_BOX_IOU_THRESHOLD)))
