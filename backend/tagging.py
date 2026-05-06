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
    for row in database.untagged_faces(conn):
        embedding = json.loads(row["embedding"] or "[]")
        if cosine(target_embedding, embedding) >= match_threshold():
            database.set_face_tag(conn, row["id"], tag, source="auto_propagated")
            changed += 1
    return changed


def tag_face(file_id: str, face_id: str, tag: str) -> dict:
    conn = database.connect()
    try:
        if not database.find_file(conn, file_id):
            return {"ok": False, "error": "File not found", "status": 404}

        clean_tag = tag.strip()
        target_embedding = database.face_embedding(conn, face_id)
        database.set_face_tag(conn, face_id, clean_tag, source="manual")
        propagated = propagate_tag(conn, target_embedding, clean_tag)
        conn.commit()
        return {"ok": True, "propagated": propagated, "files": database.list_files(conn)}
    finally:
        conn.close()
