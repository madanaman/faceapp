from __future__ import annotations

import mimetypes
from pathlib import Path

from . import database
from .config import IMAGE_SUFFIXES
from .detector import detect_faces
from .metadata import extract_photo_metadata
from .tagging import apply_known_tags


def file_signature(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"


def scan_folder(folder: Path) -> list[dict]:
    if not folder.exists() or not folder.is_dir():
        raise ValueError("Folder does not exist or is not a directory.")

    conn = database.connect()
    records = []
    auto_tagged = 0

    try:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue

            file_id = str(path.resolve())
            signature = file_signature(path)
            existing = database.find_current_file(conn, file_id, signature)
            if existing:
                record = database.photo_to_record(conn, existing)
                tagged_count = apply_known_tags(conn, record["faces"])
                if tagged_count:
                    auto_tagged += tagged_count
                    database.update_faces(conn, file_id, record["faces"])
                    conn.commit()
                    record = database.photo_to_record(conn, existing)
                if database.metadata_needs_refresh(conn, file_id):
                    metadata = extract_photo_metadata(path)
                    database.save_metadata(conn, file_id, metadata)
                    database.save_place(
                        conn,
                        file_id,
                        {
                            "latitude": metadata.get("latitude"),
                            "longitude": metadata.get("longitude"),
                            "source": "exif_gps" if metadata.get("latitude") is not None else None,
                        },
                    )
                    conn.commit()
                    record = database.photo_to_record(conn, existing)
                records.append(record)
                continue

            old_tags = database.stored_tags(conn, file_id)
            analysis = detect_faces(path)
            metadata = extract_photo_metadata(path)
            for face in analysis["faces"]:
                face["tag"] = old_tags.get(face["id"], "")
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
                "place": {
                    "latitude": metadata.get("latitude"),
                    "longitude": metadata.get("longitude"),
                    "source": "exif_gps" if metadata.get("latitude") is not None else None,
                },
            }
            database.save_file(conn, record)
            conn.commit()
            records.append(record)
    finally:
        conn.close()

    return {"files": records, "autoTagged": auto_tagged}
