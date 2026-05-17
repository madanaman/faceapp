from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "face_index.sqlite3"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
THUMBNAIL_DIR = ROOT / ".thumbnails"

ENGINE_NAME = "InsightFace buffalo_l"
REQUESTED_PROVIDERS = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
DEFAULT_MODEL = "buffalo_l"
DEFAULT_MATCH_THRESHOLD = 0.42
DEFAULT_FACE_RECONCILE_THRESHOLD = 0.85
DEFAULT_FACE_BOX_IOU_THRESHOLD = 0.7
DEFAULT_VIDEO_SAMPLE_INTERVAL_SECONDS = 3.0
DEFAULT_VIDEO_MAX_FRAMES = 300
DEFAULT_VIDEO_MIN_DETECTION_SCORE = 0.7
DEFAULT_VIDEO_MIN_FACE_HEIGHT_RATIO = 0.04
DEFAULT_VIDEO_CLUSTER_THRESHOLD = 0.42

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


def video_sample_interval_seconds() -> float:
    return float(os.environ.get("VIDEO_SAMPLE_INTERVAL_SECONDS", str(DEFAULT_VIDEO_SAMPLE_INTERVAL_SECONDS)))


def video_max_frames() -> int:
    return int(os.environ.get("VIDEO_MAX_FRAMES", str(DEFAULT_VIDEO_MAX_FRAMES)))


def video_min_detection_score() -> float:
    return float(os.environ.get("VIDEO_MIN_DETECTION_SCORE", str(DEFAULT_VIDEO_MIN_DETECTION_SCORE)))


def video_min_face_height_ratio() -> float:
    return float(os.environ.get("VIDEO_MIN_FACE_HEIGHT_RATIO", str(DEFAULT_VIDEO_MIN_FACE_HEIGHT_RATIO)))


def video_cluster_threshold() -> float:
    return float(os.environ.get("VIDEO_CLUSTER_THRESHOLD", str(DEFAULT_VIDEO_CLUSTER_THRESHOLD)))
