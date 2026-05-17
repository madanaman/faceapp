from __future__ import annotations

import hashlib
from pathlib import Path

from .config import (
    THUMBNAIL_DIR,
    video_max_frames,
    video_min_detection_score,
    video_min_face_height_ratio,
    video_sample_interval_seconds,
)
from .detector import detect_faces_in_image

SCENE_DIFFERENCE_THRESHOLD = 7.5


def analyze_video(path: Path) -> dict:
    try:
        import cv2  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("OpenCV is missing. Install `opencv-python`.") from exc

    warnings = []
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return video_failure(f"{path.name}: video could not be opened; codec may be unsupported.")

    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frame_count / fps if fps > 0 and frame_count > 0 else None
    if fps <= 0:
        fps = 30.0
        warnings.append(f"{path.name}: FPS metadata missing; sampled with 30fps fallback.")

    faces = []
    previous_signature = None
    sampled = 0
    decoded = 0
    interval = max(video_sample_interval_seconds(), 0.1)
    max_frames = max(video_max_frames(), 1)
    min_score = video_min_detection_score()
    min_face_height = height * video_min_face_height_ratio() if height else 0.0
    total_samples = estimated_sample_count(duration, interval, max_frames)

    for sample_index in range(total_samples):
        timestamp = sample_index * interval
        frame_index = int(timestamp * fps)
        if frame_count and frame_index >= frame_count:
            break
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        sampled += 1
        if not ok or frame is None:
            continue
        decoded += 1

        signature = frame_signature(frame, cv2)
        if previous_signature is not None and frame_difference(previous_signature, signature) < SCENE_DIFFERENCE_THRESHOLD:
            continue
        previous_signature = signature

        for face_index, face in enumerate(detect_faces_in_image(frame)):
            if not is_main_video_face(face, min_score, min_face_height):
                continue
            face["id"] = f"candidate-{frame_index}-{face_index}"
            face["frameIndex"] = frame_index
            face["timestampSeconds"] = timestamp
            face["thumbnail"] = save_face_thumbnail(path, frame, face, cv2)
            faces.append(face)

    capture.release()

    if sampled and not decoded:
        warnings.append(f"{path.name}: video opened but no frames could be decoded.")

    return {
        "width": width,
        "height": height,
        "durationSeconds": duration,
        "faces": faces,
        "clusters": [],
        "warnings": warnings,
    }


def estimated_sample_count(duration: float | None, interval: float, max_frames: int) -> int:
    if duration is None:
        return max_frames
    return min(max_frames, int(duration / interval) + 1)


def is_main_video_face(face: dict, min_score: float, min_face_height: float) -> bool:
    if face.get("detScore", 0.0) < min_score:
        return False
    if face.get("box", {}).get("height", 0.0) < min_face_height:
        return False
    return True


def frame_signature(frame, cv2) -> object:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (64, 36))


def frame_difference(a, b) -> float:
    return float(abs(a.astype("float32") - b.astype("float32")).mean())


def save_face_thumbnail(path: Path, frame, face: dict, cv2) -> str:
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    box = face.get("box", {})
    height, width = frame.shape[:2]
    x1 = max(0, int(box.get("x", 0)))
    y1 = max(0, int(box.get("y", 0)))
    x2 = min(width, int(box.get("x", 0) + box.get("width", 0)))
    y2 = min(height, int(box.get("y", 0) + box.get("height", 0)))
    if x2 <= x1 or y2 <= y1:
        return ""

    digest = hashlib.sha1(f"{path}:{face['id']}".encode("utf-8")).hexdigest()[:16]
    thumbnail_path = THUMBNAIL_DIR / f"{digest}.jpg"
    crop = frame[y1:y2, x1:x2]
    cv2.imwrite(str(thumbnail_path), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    return str(thumbnail_path)


def video_failure(warning: str) -> dict:
    return {
        "width": 0,
        "height": 0,
        "durationSeconds": None,
        "faces": [],
        "clusters": [],
        "warnings": [warning],
    }
