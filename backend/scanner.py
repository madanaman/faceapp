from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from . import database
from .clustering import cluster_faces, merge_clusters_by_tag
from .config import IMAGE_SUFFIXES, VIDEO_SUFFIXES
from .detector import detect_faces
from .metadata import extract_photo_metadata
from .tagging import apply_known_tags
from .video import analyze_video

MAY_REQUIRE_EXTRA_DECODER = {".heic", ".heif"}
SCAN_MODES = {"photos", "videos", "both"}
logger = logging.getLogger(__name__)


def file_signature(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"


def scan_folder(folder: Path, scan_mode: str = "photos", album_name: str = "") -> dict:
    if not folder.exists() or not folder.is_dir():
        raise ValueError("Folder does not exist or is not a directory.")
    if scan_mode not in SCAN_MODES:
        raise ValueError("Scan mode must be photos, videos, or both.")

    records = []
    auto_tagged = 0
    warnings = []
    clean_album_name = album_name.strip()
    logger.info("Scanning folder=%s mode=%s album=%s", folder, scan_mode, clean_album_name)

    with database.connection() as conn:
        album = None
        if clean_album_name:
            with conn:
                album = database.create_album(conn, clean_album_name)
                logger.info("Scan album ready name=%s id=%s", clean_album_name, album["id"])

        for path in sorted(folder.rglob("*")):
            if not should_scan_path(path, scan_mode):
                continue
            logger.debug("Scanning file path=%s", path)
            if path.suffix.lower() in MAY_REQUIRE_EXTRA_DECODER:
                warnings.append(f"{path.name}: HEIC/HEIF support depends on local OpenCV/Pillow codecs.")

            file_id = str(path.resolve())
            signature = file_signature(path)
            with conn:
                existing = database.find_current_file(conn, file_id, signature)
                if existing:
                    logger.debug("Using existing indexed file path=%s", path)
                    record = database.photo_to_record(conn, existing)
                    tagged_count = apply_known_tags(conn, record["faces"])
                    if tagged_count:
                        auto_tagged += tagged_count
                        persist_face_tags(conn, record["faces"])
                        logger.info("Auto-tagged existing file path=%s faces=%s", path, tagged_count)
                        record = database.photo_to_record(conn, existing)
                    if database.metadata_needs_refresh(conn, file_id):
                        metadata = extract_photo_metadata(path) if is_image(path) else {}
                        database.save_metadata(conn, file_id, metadata)
                        database.save_place(conn, file_id, gps_place(metadata))
                        record = database.photo_to_record(conn, existing)
                    if album:
                        database.add_photo_to_album(conn, album["id"], file_id)
                        logger.debug("Added existing file to album path=%s album=%s", path, album["name"])
                        record = database.photo_to_record(conn, existing)
                    records.append(record)
                    continue

                analysis = analyze_path(path)
                warnings.extend(analysis.get("warnings", []))
                if not analysis["width"] or not analysis["height"]:
                    warnings.append(f"{path.name}: skipped because it could not be decoded.")
                    logger.warning("Skipped undecodable file path=%s", path)
                    continue

                analysis["faces"] = database.filter_ignored_faces(conn, file_id, analysis["faces"])
                analysis["clusters"] = cluster_faces(analysis["faces"]) if is_video(path) else []
                # Video container timestamps are not extracted yet; video date
                # filters currently rely on the file name/signature metadata.
                metadata = extract_photo_metadata(path) if is_image(path) else {}
                auto_tagged += apply_known_tags(conn, analysis["faces"])
                propagate_cluster_tags(analysis["faces"])
                analysis["clusters"] = merge_clusters_by_tag(analysis["clusters"]) if is_video(path) else []
                logger.info(
                    "Analyzed file path=%s faces=%s clusters=%s auto_tagged_total=%s",
                    path,
                    len(analysis["faces"]),
                    len(analysis.get("clusters", [])),
                    auto_tagged,
                )

                record = {
                    "id": file_id,
                    "name": path.name,
                    "path": file_id,
                    "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "signature": signature,
                    "width": analysis["width"],
                    "height": analysis["height"],
                    "durationSeconds": analysis.get("durationSeconds"),
                    "faces": analysis["faces"],
                    "clusters": analysis.get("clusters", []),
                    "metadata": metadata,
                    "place": gps_place(metadata),
                }
                database.save_file(conn, record)
                if album:
                    database.add_photo_to_album(conn, album["id"], file_id)
                    logger.debug("Added scanned file to album path=%s album=%s", path, album["name"])
                    record = database.photo_to_record(conn, database.find_file(conn, file_id))
                records.append(record)

        logger.info(
            "Scan finished folder=%s files=%s auto_tagged=%s warnings=%s",
            folder,
            len(records),
            auto_tagged,
            len(warnings),
        )
        return {
            "files": records,
            "autoTagged": auto_tagged,
            "warnings": warnings,
            "albums": database.list_albums(conn),
            "tags": database.list_tags(conn),
        }


def rescan_photo(file_id: str, reset_ignored: bool = False) -> dict:
    path = Path(file_id)
    if not path.exists() or not path.is_file():
        raise ValueError("File does not exist.")

    warnings = []
    auto_tagged = 0
    signature = file_signature(path)
    logger.info("Rescanning file=%s reset_ignored=%s", file_id, reset_ignored)

    with database.connection() as conn:
        if not database.find_file(conn, file_id):
            raise ValueError("File is not indexed.")

        with conn:
            if reset_ignored:
                database.clear_ignored_faces(conn, file_id)
                logger.info("Cleared ignored faces file=%s", file_id)

            analysis = analyze_path(path)
            warnings.extend(analysis.get("warnings", []))
            if not analysis["width"] or not analysis["height"]:
                logger.warning("Rescan failed decode file=%s", file_id)
                raise ValueError("File could not be decoded.")

            analysis["faces"] = database.filter_ignored_faces(conn, file_id, analysis["faces"])
            analysis["clusters"] = cluster_faces(analysis["faces"]) if is_video(path) else []
            # Video container timestamps are not extracted yet; video date
            # filters currently rely on the file name/signature metadata.
            metadata = extract_photo_metadata(path) if is_image(path) else {}
            auto_tagged += apply_known_tags(conn, analysis["faces"])
            propagate_cluster_tags(analysis["faces"])
            analysis["clusters"] = merge_clusters_by_tag(analysis["clusters"]) if is_video(path) else []
            record = {
                "id": file_id,
                "name": path.name,
                "path": file_id,
                "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "signature": signature,
                "width": analysis["width"],
                "height": analysis["height"],
                "durationSeconds": analysis.get("durationSeconds"),
                "faces": analysis["faces"],
                "clusters": analysis.get("clusters", []),
                "metadata": metadata,
                "place": gps_place(metadata),
            }
            database.save_file(conn, record)
            logger.info(
                "Rescan analyzed file=%s faces=%s clusters=%s auto_tagged=%s",
                file_id,
                len(analysis["faces"]),
                len(analysis.get("clusters", [])),
                auto_tagged,
            )

        return {"files": database.list_files(conn), "autoTagged": auto_tagged, "warnings": warnings}


def gps_place(metadata: dict) -> dict:
    return {
        "latitude": metadata.get("latitude"),
        "longitude": metadata.get("longitude"),
        "source": "exif_gps" if metadata.get("latitude") is not None else None,
    }


def should_scan_path(path: Path, scan_mode: str) -> bool:
    if not path.is_file():
        return False
    suffix = path.suffix.lower()
    return (scan_mode in {"photos", "both"} and suffix in IMAGE_SUFFIXES) or (
        scan_mode in {"videos", "both"} and suffix in VIDEO_SUFFIXES
    )


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_SUFFIXES


def analyze_path(path: Path) -> dict:
    if is_video(path):
        return analyze_video(path)
    return detect_faces(path)


def propagate_cluster_tags(faces: list[dict]) -> None:
    cluster_tags = {}
    for face in faces:
        cluster_id = face.get("clusterId")
        if cluster_id and face.get("tag"):
            cluster_tags.setdefault(cluster_id, face["tag"])

    for face in faces:
        cluster_id = face.get("clusterId")
        if cluster_id in cluster_tags and not face.get("tag"):
            face["tag"] = cluster_tags[cluster_id]
            face["tagSource"] = "auto_propagated"


def persist_face_tags(conn, faces: list[dict]) -> None:
    for face in faces:
        if face.get("tag"):
            database.set_face_tag(conn, face["id"], face["tag"], source=face.get("tagSource") or "auto_propagated")
