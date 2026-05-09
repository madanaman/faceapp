from __future__ import annotations

from pathlib import Path

from .config import ENGINE_NAME, REQUESTED_PROVIDERS, model_name

FACE_APP = None


def ensure_detector():
    global FACE_APP
    if FACE_APP is not None:
        return FACE_APP

    try:
        try:
            from insightedge.app import FaceAnalysis  # type: ignore
        except ModuleNotFoundError:
            from insightface.app import FaceAnalysis  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "InsightEdge/InsightFace dependencies are missing. Install them with "
            "`python3 -m pip install insightface onnxruntime opencv-python`."
        ) from exc

    import onnxruntime  # type: ignore

    available = set(onnxruntime.get_available_providers())
    providers = [provider for provider in REQUESTED_PROVIDERS if provider in available]
    if "CPUExecutionProvider" not in providers:
        providers.append("CPUExecutionProvider")

    FACE_APP = FaceAnalysis(name=model_name(), providers=providers)
    FACE_APP.prepare(ctx_id=-1, det_size=(640, 640))
    return FACE_APP


def dependency_status() -> tuple[bool, str]:
    try:
        try:
            __import__("insightedge.app")
        except ModuleNotFoundError:
            __import__("insightface.app")
        __import__("onnxruntime")
        __import__("cv2")
    except ModuleNotFoundError:
        return False, (
            "InsightEdge/InsightFace dependencies are missing. Install them with "
            "`python3 -m pip install insightface onnxruntime opencv-python`."
        )
    return True, ""


def available_providers() -> list[str]:
    try:
        import onnxruntime  # type: ignore

        return list(onnxruntime.get_available_providers())
    except ModuleNotFoundError:
        return []


def health_payload() -> dict:
    ok, error = dependency_status()
    return {
        "ok": ok,
        "engine": ENGINE_NAME,
        "providers": available_providers(),
        "requestedProviders": REQUESTED_PROVIDERS,
        "error": error,
    }


def detect_faces(path: Path) -> dict:
    try:
        import cv2  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("OpenCV is missing. Install `opencv-python`.") from exc

    app = ensure_detector()
    image = cv2.imread(str(path))
    if image is None:
        return {"width": 0, "height": 0, "faces": []}

    height, width = image.shape[:2]
    faces = []
    for index, face in enumerate(app.get(image)):
        x1, y1, x2, y2 = [float(value) for value in face.bbox]
        x1 = max(0.0, min(x1, float(width)))
        y1 = max(0.0, min(y1, float(height)))
        x2 = max(0.0, min(x2, float(width)))
        y2 = max(0.0, min(y2, float(height)))
        faces.append(
            {
                "id": f"candidate-{index}",
                "box": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                "embedding": [float(value) for value in getattr(face, "normed_embedding", [])],
                "tag": "",
                "thumbnail": "",  # Keep future thumbnails as file paths, not base64 blobs.
            }
        )
    return {"width": width, "height": height, "faces": faces}
