from __future__ import annotations

import math
from uuid import uuid4

from .config import video_cluster_threshold
from .tagging import embedding_similarity


def cluster_faces(faces: list[dict], threshold: float | None = None) -> list[dict]:
    threshold = video_cluster_threshold() if threshold is None else threshold
    clusters: list[dict] = []
    for face in faces:
        embedding = face.get("embedding", [])
        if not embedding:
            continue

        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            score = embedding_similarity(embedding, cluster["centroid"])
            if score > best_score:
                best_cluster = cluster
                best_score = score

        if best_cluster and best_score >= threshold:
            best_cluster["faces"].append(face)
            best_cluster["centroid"] = centroid_for_faces(best_cluster["faces"])
            continue

        clusters.append(
            {
                "id": f"cluster-{uuid4().hex}",
                "faces": [face],
                "centroid": list(embedding),
            }
        )

    return merge_similar_clusters(clusters, threshold)


def merge_similar_clusters(clusters: list[dict], threshold: float) -> list[dict]:
    merged = True
    while merged:
        merged = False
        for left_index, left in enumerate(clusters):
            for right_index in range(left_index + 1, len(clusters)):
                right = clusters[right_index]
                if embedding_similarity(left.get("centroid", []), right.get("centroid", [])) >= threshold:
                    merge_cluster(left, right)
                    del clusters[right_index]
                    merged = True
                    break
            if merged:
                break

    for cluster in clusters:
        finalize_cluster(cluster)
    return clusters


def merge_clusters_by_tag(clusters: list[dict]) -> list[dict]:
    tagged_clusters = {}
    merged_clusters = []
    for cluster in clusters:
        tag_key = cluster_tag_key(cluster)
        if not tag_key:
            merged_clusters.append(cluster)
            continue
        if tag_key in tagged_clusters:
            merge_cluster(tagged_clusters[tag_key], cluster)
        else:
            tagged_clusters[tag_key] = cluster
            merged_clusters.append(cluster)

    for cluster in merged_clusters:
        finalize_cluster(cluster)
    return merged_clusters


def merge_cluster(target: dict, source: dict) -> None:
    target["faces"].extend(source.get("faces", []))
    target["centroid"] = centroid_for_faces(target["faces"])


def cluster_tag_key(cluster: dict) -> str:
    for face in cluster.get("faces", []):
        tag = (face.get("tag") or "").strip().lower()
        if tag:
            return tag
    return ""


def finalize_cluster(cluster: dict) -> None:
    faces = cluster["faces"]
    representative = max(faces, key=lambda face: face.get("detScore", 0.0))
    cluster["representativeFaceId"] = representative["id"]
    cluster["representativeTimestampSeconds"] = representative.get("timestampSeconds")
    cluster["faceCount"] = len(faces)
    timestamps = [face.get("timestampSeconds") for face in faces if face.get("timestampSeconds") is not None]
    cluster["firstSeenSeconds"] = min(timestamps) if timestamps else None
    cluster["lastSeenSeconds"] = max(timestamps) if timestamps else None
    for face in faces:
        face["clusterId"] = cluster["id"]
        face["appearanceCount"] = len(faces)


def centroid_for_faces(faces: list[dict]) -> list[float]:
    embeddings = [face.get("embedding", []) for face in faces if face.get("embedding")]
    if not embeddings:
        return []
    size = len(embeddings[0])
    totals = [0.0] * size
    for embedding in embeddings:
        if len(embedding) != size:
            continue
        for index, value in enumerate(embedding):
            totals[index] += float(value)
    return normalize([value / len(embeddings) for value in totals])


def normalize(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if not magnitude:
        return values
    return [value / magnitude for value in values]
