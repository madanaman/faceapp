from __future__ import annotations

import mimetypes
from pathlib import Path

from . import database
from .config import IMAGE_SUFFIXES
from .detector import detect_faces
from .metadata import extract_photo_metadata
from .tagging import apply_known_tags

MAY_REQUIRE_EXTRA_DECODER = {".heic", ".heif"}


def file_signature(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"


def scan_folder(folder: Path) -> dict:
    if not folder.exists() or not folder.is_dir():
        raise ValueError("Folder does not exist or is not a directory.")

    records = []
    auto_tagged = 0
    warnings = []

    with database.connection() as conn:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if path.suffix.lower() in MAY_REQUIRE_EXTRA_DECODER:
                warnings.append(f"{path.name}: HEIC/HEIF support depends on local OpenCV/Pillow codecs.")

            file_id = str(path.resolve())
            signature = file_signature(path)
            with conn:
                existing = database.find_current_file(conn, file_id, signature)
                if existing:
                    record = database.photo_to_record(conn, existing)
                    tagged_count = apply_known_tags(conn, record["faces"])
                    if tagged_count:
                        auto_tagged += tagged_count
                        database.update_faces(conn, file_id, record["faces"])
                        record = database.photo_to_record(conn, existing)
                    if database.metadata_needs_refresh(conn, file_id):
                        metadata = extract_photo_metadata(path)
                        database.save_metadata(conn, file_id, metadata)
                        database.save_place(conn, file_id, gps_place(metadata))
                        record = database.photo_to_record(conn, existing)
                    records.append(record)
                    continue

                analysis = detect_faces(path)
                if not analysis["width"] or not analysis["height"]:
                    warnings.append(f"{path.name}: skipped because it could not be decoded.")
                    continue

                analysis["faces"] = database.filter_ignored_faces(conn, file_id, analysis["faces"])
                metadata = extract_photo_metadata(path)
                auto_tagged += apply_known_tags(conn, analysis["faces"])

                record = {
                    "id": file_id,
                    "name": path.name,
                    "path": file_id,
                    "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "signature": signature,
                    "width": analysis["width"],
                    "height": analysis["height"],
                    "faces": analysis["faces"],
                    "metadata": metadata,
                    "place": gps_place(metadata),
                }
                database.save_file(conn, record)
                records.append(record)

    return {"files": records, "autoTagged": auto_tagged, "warnings": warnings}


def rescan_photo(file_id: str, reset_ignored: bool = False) -> dict:
    path = Path(file_id)
    if not path.exists() or not path.is_file():
        raise ValueError("Photo file does not exist.")

    warnings = []
    auto_tagged = 0
    signature = file_signature(path)

    with database.connection() as conn:
        if not database.find_file(conn, file_id):
            raise ValueError("Photo is not indexed.")

        with conn:
            if reset_ignored:
                database.clear_ignored_faces(conn, file_id)

            analysis = detect_faces(path)
            if not analysis["width"] or not analysis["height"]:
                raise ValueError("Photo could not be decoded.")

            analysis["faces"] = database.filter_ignored_faces(conn, file_id, analysis["faces"])
            metadata = extract_photo_metadata(path)
            auto_tagged += apply_known_tags(conn, analysis["faces"])
            record = {
                "id": file_id,
                "name": path.name,
                "path": file_id,
                "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "signature": signature,
                "width": analysis["width"],
                "height": analysis["height"],
                "faces": analysis["faces"],
                "metadata": metadata,
                "place": gps_place(metadata),
            }
            database.save_file(conn, record)

        return {"files": database.list_files(conn), "autoTagged": auto_tagged, "warnings": warnings}


def gps_place(metadata: dict) -> dict:
    return {
        "latitude": metadata.get("latitude"),
        "longitude": metadata.get("longitude"),
        "source": "exif_gps" if metadata.get("latitude") is not None else None,
    }
