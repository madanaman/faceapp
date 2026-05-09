from __future__ import annotations

import json

from . import database
from .config import match_threshold


def embedding_similarity(a: list[float], b: list[float]) -> float:
    # InsightFace normed_embedding is L2-normalized, so dot product equals cosine similarity.
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def propagate_tag(conn, target_embedding: list[float], tag: str) -> int:
    if not target_embedding or not tag:
        return 0

    changed = 0
    for row in database.untagged_faces(conn):
        embedding = json.loads(row["embedding"] or "[]")
        if embedding_similarity(target_embedding, embedding) >= match_threshold():
            database.set_face_tag(conn, row["id"], tag, source="auto_propagated")
            changed += 1
    return changed


def best_known_tag(conn, embedding: list[float]) -> str:
    if not embedding:
        return ""

    best_tag = ""
    best_score = 0.0
    for candidate in database.tagged_face_embeddings(conn):
        score = embedding_similarity(embedding, candidate["embedding"])
        if score > best_score:
            best_score = score
            best_tag = candidate["tag"]

    return best_tag if best_score >= match_threshold() else ""


def apply_known_tags(conn, faces: list[dict]) -> int:
    changed = 0
    for face in faces:
        if face.get("tag"):
            continue
        tag = best_known_tag(conn, face.get("embedding", []))
        if tag:
            face["tag"] = tag
            changed += 1
    return changed


def tag_face(file_id: str, face_id: str, tag: str) -> dict:
    with database.connection() as conn:
        if not database.find_file(conn, file_id):
            return {"ok": False, "error": "File not found", "status": 404}

        with conn:
            clean_tag = tag.strip()
            target_embedding = database.face_embedding(conn, face_id)
            database.set_face_tag(conn, face_id, clean_tag, source="manual")
            propagated = propagate_tag(conn, target_embedding, clean_tag)
        return {"ok": True, "propagated": propagated, "files": database.list_files(conn)}
