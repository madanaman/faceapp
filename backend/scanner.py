from __future__ import annotations

import mimetypes
from pathlib import Path

from . import database
from .config import IMAGE_SUFFIXES
from .detector import detect_faces


def file_signature(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"


def scan_folder(folder: Path) -> list[dict]:
    if not folder.exists() or not folder.is_dir():
        raise ValueError("Folder does not exist or is not a directory.")

    conn = database.connect()
    records = []

    try:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue

            file_id = str(path.resolve())
            signature = file_signature(path)
            existing = database.find_current_file(conn, file_id, signature)
            if existing:
                records.append(database.row_to_record(existing))
                continue

            old_tags = database.stored_tags(conn, file_id)
            analysis = detect_faces(path)
            for face in analysis["faces"]:
                face["tag"] = old_tags.get(face["id"], "")

            record = {
                "id": file_id,
                "name": path.name,
                "path": file_id,
                "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "signature": signature,
                "width": analysis["width"],
                "height": analysis["height"],
                "faces": analysis["faces"],
            }
            database.save_file(conn, record)
            conn.commit()
            records.append(record)
    finally:
        conn.close()

    return records
