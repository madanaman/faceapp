from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = Path(getattr(sys, "_MEIPASS", ROOT))


def default_app_data_dir() -> Path:
    override = os.environ.get("LOCAL_FACE_APP_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if os.environ.get("LOCAL_FACE_PACKAGED") != "1":
        return ROOT
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Local Face Photos"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Local Face Photos"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "local-face-photos"


APP_DATA_DIR = default_app_data_dir()
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DATA_DIR / "face_index.sqlite3"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
THUMBNAIL_DIR = APP_DATA_DIR / ".thumbnails"
LOG_DIR = APP_DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "faceapp.log"

ENGINE_NAME = "InsightFace buffalo_l"
DEFAULT_MODEL = "buffalo_l"
DEFAULT_MATCH_THRESHOLD = 0.42
DEFAULT_FACE_RECONCILE_THRESHOLD = 0.85
DEFAULT_FACE_BOX_IOU_THRESHOLD = 0.7
DEFAULT_VIDEO_SAMPLE_INTERVAL_SECONDS = 3.0
DEFAULT_VIDEO_MAX_FRAMES = 300
DEFAULT_VIDEO_MIN_DETECTION_SCORE = 0.7
DEFAULT_VIDEO_MIN_FACE_HEIGHT_RATIO = 0.04
DEFAULT_VIDEO_CLUSTER_THRESHOLD = 0.42
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_RETENTION_DAYS = 3

os.environ.setdefault("MPLCONFIGDIR", str(APP_DATA_DIR / ".cache" / "matplotlib"))
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")


def requested_providers() -> list[str]:
    configured = os.environ.get("INSIGHTFACE_PROVIDERS")
    if configured:
        return [provider.strip() for provider in configured.split(",") if provider.strip()]
    if sys.platform == "darwin":
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


REQUESTED_PROVIDERS = requested_providers()


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


def log_level() -> str:
    return os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()


def log_retention_days() -> int:
    return int(os.environ.get("LOG_RETENTION_DAYS", str(DEFAULT_LOG_RETENTION_DAYS)))
