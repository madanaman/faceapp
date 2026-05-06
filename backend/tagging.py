from __future__ import annotations

import json

from . import database
from .config import match_threshold


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def propagate_tag(conn, target_embedding: list[float], tag: str) -> int:
    if not target_embedding or not tag:
        return 0

    changed = 0
    rows = conn.execute("select id, faces from files").fetchall()
    for row in rows:
        faces = json.loads(row["faces"])
        touched = False
        for face in faces:
            if face.get("tag"):
                continue
            if cosine(target_embedding, face.get("embedding", [])) >= match_threshold():
                face["tag"] = tag
                changed += 1
                touched = True
        if touched:
            database.update_faces(conn, row["id"], faces)
    return changed


def tag_face(file_id: str, face_id: str, tag: str) -> dict:
    conn = database.connect()
    try:
        row = database.find_file(conn, file_id)
        if not row:
            return {"ok": False, "error": "File not found", "status": 404}

        faces = json.loads(row["faces"])
        target_embedding = []
        clean_tag = tag.strip()
        for face in faces:
            if face["id"] == face_id:
                face["tag"] = clean_tag
                target_embedding = face.get("embedding", [])

        database.update_faces(conn, file_id, faces)
        propagated = propagate_tag(conn, target_embedding, clean_tag)
        conn.commit()
        return {"ok": True, "propagated": propagated, "files": database.list_files(conn)}
    finally:
        conn.close()
