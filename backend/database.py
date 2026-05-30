from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from .config import DB_PATH, face_box_iou_threshold, face_reconcile_threshold, match_threshold

SCHEMA_VERSION = 6


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma busy_timeout = 5000")
    conn.execute("pragma journal_mode = wal")
    ensure_schema(conn)
    run_migrations(conn)
    return conn


@contextmanager
def connection():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists photos (
            id text primary key,
            path text not null,
            name text not null,
            type text not null,
            signature text not null,
            width real,
            height real,
            duration_seconds real,
            indexed_at text not null
        );

        create table if not exists faces (
            id text primary key,
            photo_id text not null references photos(id) on delete cascade,
            box_x real not null,
            box_y real not null,
            box_width real not null,
            box_height real not null,
            cluster_id text,
            frame_index integer,
            timestamp_seconds real,
            det_score real,
            embedding text,
            thumbnail text
        );

        create table if not exists face_clusters (
            id text primary key,
            photo_id text not null references photos(id) on delete cascade,
            centroid text,
            representative_face_id text,
            representative_timestamp_seconds real,
            face_count integer not null default 0,
            first_seen_seconds real,
            last_seen_seconds real
        );

        create table if not exists people (
            id integer primary key autoincrement,
            name text not null unique,
            created_at text not null
        );

        create table if not exists face_people (
            face_id text not null references faces(id) on delete cascade,
            person_id integer not null references people(id) on delete cascade,
            confidence real,
            source text not null,
            primary key (face_id, person_id)
        );

        create table if not exists ignored_faces (
            id integer primary key autoincrement,
            photo_id text not null references photos(id) on delete cascade,
            box_x real not null,
            box_y real not null,
            box_width real not null,
            box_height real not null,
            embedding text,
            ignored_tag text,
            created_at text not null
        );

        create table if not exists photo_metadata (
            photo_id text primary key references photos(id) on delete cascade,
            taken_at text,
            camera_make text,
            camera_model text,
            latitude real,
            longitude real,
            altitude real,
            orientation integer,
            exif_json text not null default '{}'
        );

        create table if not exists photo_places (
            photo_id text primary key references photos(id) on delete cascade,
            city text,
            region text,
            country text,
            latitude real,
            longitude real,
            source text
        );

        create table if not exists albums (
            id integer primary key autoincrement,
            name text not null collate nocase unique,
            description text,
            cover_photo_id text references photos(id) on delete set null,
            created_at text not null,
            updated_at text not null
        );

        create table if not exists album_photos (
            album_id integer not null references albums(id) on delete cascade,
            photo_id text not null references photos(id) on delete cascade,
            added_at text not null,
            sort_order integer,
            primary key (album_id, photo_id)
        );

        create table if not exists photo_tags (
            id integer primary key autoincrement,
            name text not null collate nocase unique,
            kind text not null default 'custom',
            created_at text not null
        );

        create table if not exists photo_tag_links (
            photo_id text not null references photos(id) on delete cascade,
            tag_id integer not null references photo_tags(id) on delete cascade,
            created_at text not null,
            primary key (photo_id, tag_id)
        );

        create index if not exists idx_photos_signature on photos(signature);
        create index if not exists idx_faces_photo_id on faces(photo_id);
        create index if not exists idx_face_clusters_photo_id on face_clusters(photo_id);
        create index if not exists idx_photo_metadata_taken_at on photo_metadata(taken_at);
        create index if not exists idx_photo_metadata_lat_lon on photo_metadata(latitude, longitude);
        create index if not exists idx_photo_places_city on photo_places(city);
        create index if not exists idx_face_people_person_id on face_people(person_id);
        create index if not exists idx_ignored_faces_photo_id on ignored_faces(photo_id);
        create index if not exists idx_album_photos_photo_id on album_photos(photo_id);
        create index if not exists idx_photo_tag_links_tag_id on photo_tag_links(tag_id);
        """
    )

def run_migrations(conn: sqlite3.Connection) -> None:
    version = conn.execute("pragma user_version").fetchone()[0]
    if version < 1:
        migrate_legacy_files(conn)
    if version < 2:
        add_column_if_missing(conn, "ignored_faces", "ignored_tag", "text")
    if version < 4:
        add_column_if_missing(conn, "faces", "cluster_id", "text")
        add_column_if_missing(conn, "faces", "frame_index", "integer")
        add_column_if_missing(conn, "faces", "timestamp_seconds", "real")
        add_column_if_missing(conn, "faces", "det_score", "real")
    if version < 5:
        add_column_if_missing(conn, "photos", "duration_seconds", "real")
    if version != SCHEMA_VERSION:
        conn.execute(f"pragma user_version = {SCHEMA_VERSION}")
    # Legacy databases may not have faces.cluster_id until the migrations above.
    conn.execute("create index if not exists idx_faces_cluster_id on faces(cluster_id)")
    conn.commit()


def migrate_legacy_files(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "files"):
        return

    legacy_rows = conn.execute("select * from files").fetchall()
    if not legacy_rows:
        return

    for row in legacy_rows:
        if conn.execute("select 1 from photos where id = ?", (row["id"],)).fetchone():
            continue
        record = {
            "id": row["id"],
            "name": row["name"],
            "path": row["path"],
            "type": row["type"],
            "signature": row["signature"],
            "width": row["width"],
            "height": row["height"],
            "faces": json.loads(row["faces"]),
            "metadata": {},
            "place": {},
        }
        save_file(conn, record)
    conn.commit()


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            "select 1 from sqlite_master where type = 'table' and name = ?",
            (table_name,),
        ).fetchone()
    )


def add_column_if_missing(conn: sqlite3.Connection, table_name: str, column_name: str, column_def: str) -> None:
    columns = {row["name"] for row in conn.execute(f"pragma table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"alter table {table_name} add column {column_name} {column_def}")


def list_files(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("select * from photos order by name").fetchall()
    return [photo_to_record(conn, row) for row in rows]


def search_files(
    conn: sqlite3.Connection,
    year: str | None = None,
    city: str | None = None,
    album: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    clauses = []
    params = []

    if year:
        if not year.isdigit() or len(year) != 4:
            raise ValueError("year must use YYYY format")
        clauses.append("m.taken_at >= ? and m.taken_at < ?")
        params.extend([f"{year}-01-01", f"{int(year) + 1}-01-01"])

    if city:
        clauses.append("lower(pl.city) = lower(?)")
        params.append(city)

    if album:
        clauses.append(
            """
            exists (
                select 1
                from album_photos ap
                join albums a on a.id = ap.album_id
                where ap.photo_id = p.id and lower(a.name) = lower(?)
            )
            """
        )
        params.append(album)

    if tag:
        clauses.append(
            """
            exists (
                select 1
                from photo_tag_links ptl
                join photo_tags pt on pt.id = ptl.tag_id
                where ptl.photo_id = p.id and lower(pt.name) = lower(?)
            )
            """
        )
        params.append(tag)

    where = f"where {' and '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        select distinct p.*
        from photos p
        left join photo_metadata m on m.photo_id = p.id
        left join photo_places pl on pl.photo_id = p.id
        {where}
        order by coalesce(m.taken_at, p.indexed_at) desc, p.name
        """,
        params,
    ).fetchall()
    return [photo_to_record(conn, row) for row in rows]


def find_file(conn: sqlite3.Connection, file_id: str) -> sqlite3.Row | None:
    return conn.execute("select * from photos where id = ?", (file_id,)).fetchone()


def find_current_file(conn: sqlite3.Connection, file_id: str, signature: str) -> sqlite3.Row | None:
    return conn.execute(
        "select * from photos where id = ? and signature = ?",
        (file_id, signature),
    ).fetchone()


def list_albums(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        select a.*, count(ap.photo_id) as photo_count
        from albums a
        left join album_photos ap on ap.album_id = a.id
        group by a.id
        order by lower(a.name)
        """
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"] or "",
            "coverPhotoId": row["cover_photo_id"] or "",
            "photoCount": row["photo_count"],
        }
        for row in rows
    ]


def create_album(conn: sqlite3.Connection, name: str, description: str = "") -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Album name is required")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        insert into albums (name, description, created_at, updated_at)
        values (?, ?, ?, ?)
        on conflict(name) do update set
            description = case
                when excluded.description != '' then excluded.description
                else albums.description
            end,
            updated_at = excluded.updated_at
        """,
        (clean_name, description.strip(), now, now),
    )
    row = conn.execute("select id from albums where name = ? collate nocase", (clean_name,)).fetchone()
    return next(album for album in list_albums(conn) if album["id"] == row["id"])


def list_photo_albums(conn: sqlite3.Connection, photo_id: str) -> list[dict]:
    rows = conn.execute(
        """
        select a.id, a.name
        from albums a
        join album_photos ap on ap.album_id = a.id
        where ap.photo_id = ?
        order by lower(a.name)
        """,
        (photo_id,),
    ).fetchall()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


def add_photo_to_album(conn: sqlite3.Connection, album_id: int, photo_id: str) -> None:
    if not find_file(conn, photo_id):
        raise ValueError("Photo not found")
    if not conn.execute("select 1 from albums where id = ?", (album_id,)).fetchone():
        raise ValueError("Album not found")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "insert or ignore into album_photos (album_id, photo_id, added_at) values (?, ?, ?)",
        (album_id, photo_id, now),
    )
    conn.execute("update albums set updated_at = ? where id = ?", (now, album_id))


def remove_photo_from_album(conn: sqlite3.Connection, album_id: int, photo_id: str) -> None:
    conn.execute("delete from album_photos where album_id = ? and photo_id = ?", (album_id, photo_id))


def list_tags(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        select pt.*, count(ptl.photo_id) as photo_count
        from photo_tags pt
        left join photo_tag_links ptl on ptl.tag_id = pt.id
        group by pt.id
        order by lower(pt.name)
        """
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "kind": row["kind"],
            "photoCount": row["photo_count"],
        }
        for row in rows
    ]


def create_photo_tag(conn: sqlite3.Connection, name: str, kind: str = "custom") -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Photo tag is required")
    clean_kind = kind.strip() or "custom"
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "insert or ignore into photo_tags (name, kind, created_at) values (?, ?, ?)",
        (clean_name, clean_kind, now),
    )
    row = conn.execute("select id from photo_tags where name = ? collate nocase", (clean_name,)).fetchone()
    return next(tag for tag in list_tags(conn) if tag["id"] == row["id"])


def list_photo_tags(conn: sqlite3.Connection, photo_id: str) -> list[dict]:
    rows = conn.execute(
        """
        select pt.id, pt.name, pt.kind
        from photo_tags pt
        join photo_tag_links ptl on ptl.tag_id = pt.id
        where ptl.photo_id = ?
        order by lower(pt.name)
        """,
        (photo_id,),
    ).fetchall()
    return [{"id": row["id"], "name": row["name"], "kind": row["kind"]} for row in rows]


def add_photo_tag(conn: sqlite3.Connection, photo_id: str, name: str, kind: str = "custom") -> None:
    if not find_file(conn, photo_id):
        raise ValueError("Photo not found")
    tag = create_photo_tag(conn, name, kind=kind)
    conn.execute(
        "insert or ignore into photo_tag_links (photo_id, tag_id, created_at) values (?, ?, ?)",
        (photo_id, tag["id"], datetime.now(UTC).isoformat(timespec="seconds")),
    )


def remove_photo_tag(conn: sqlite3.Connection, photo_id: str, tag_id: int) -> None:
    conn.execute("delete from photo_tag_links where photo_id = ? and tag_id = ?", (photo_id, tag_id))


def photo_to_record(conn: sqlite3.Connection, photo_row: sqlite3.Row) -> dict:
    metadata = conn.execute("select * from photo_metadata where photo_id = ?", (photo_row["id"],)).fetchone()
    place = conn.execute("select * from photo_places where photo_id = ?", (photo_row["id"],)).fetchone()
    return {
        "id": photo_row["id"],
        "name": photo_row["name"],
        "path": photo_row["path"],
        "type": photo_row["type"],
        "signature": photo_row["signature"],
        "width": photo_row["width"],
        "height": photo_row["height"],
        "durationSeconds": photo_row["duration_seconds"] if "duration_seconds" in photo_row.keys() else None,
        "faces": list_faces(conn, photo_row["id"]),
        "albums": list_photo_albums(conn, photo_row["id"]),
        "tags": list_photo_tags(conn, photo_row["id"]),
        "metadata": row_dict(metadata) if metadata else {},
        "place": row_dict(place) if place else {},
    }


def list_faces(conn: sqlite3.Connection, photo_id: str) -> list[dict]:
    # Clustered videos expose only the representative face to the UI/API. Tagging
    # and ignore operations expand back to all cluster members via cluster_id.
    rows = conn.execute(
        """
        with cluster_tags as (
            select
                f2.cluster_id,
                coalesce(
                    max(case when fp2.source = 'manual' then p2.name end),
                    max(p2.name)
                ) as cluster_tag,
                coalesce(
                    max(case when fp2.source = 'manual' then fp2.source end),
                    max(fp2.source)
                ) as cluster_tag_source
            from faces f2
            left join face_people fp2 on fp2.face_id = f2.id
            left join people p2 on p2.id = fp2.person_id
            where f2.photo_id = ?
              and f2.cluster_id is not null
            group by f2.cluster_id
        )
        select
            f.*,
            case
                when ct.cluster_tag_source = 'manual' then ct.cluster_tag
                else coalesce(p.name, ct.cluster_tag)
            end as tag,
            case
                when ct.cluster_tag_source = 'manual' then ct.cluster_tag_source
                else coalesce(fp.source, ct.cluster_tag_source)
            end as tag_source,
            fc.face_count as cluster_face_count,
            fc.representative_timestamp_seconds as cluster_representative_timestamp_seconds
        from faces f
        left join face_clusters fc on fc.id = f.cluster_id
        left join cluster_tags ct on ct.cluster_id = f.cluster_id
        left join face_people fp on fp.face_id = f.id
        left join people p on p.id = fp.person_id
        where f.photo_id = ?
          and (f.cluster_id is null or fc.representative_face_id = f.id)
        order by f.id
        """,
        (photo_id, photo_id),
    ).fetchall()
    return [face_to_record(row) for row in rows]


def face_to_record(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "box": {
            "x": row["box_x"],
            "y": row["box_y"],
            "width": row["box_width"],
            "height": row["box_height"],
        },
        "clusterId": row["cluster_id"] or "",
        "frameIndex": row["frame_index"],
        "timestampSeconds": row["timestamp_seconds"],
        "detScore": row["det_score"],
        "appearanceCount": row["cluster_face_count"] or 1,
        "representativeTimestampSeconds": row["cluster_representative_timestamp_seconds"],
        "embedding": json.loads(row["embedding"] or "[]"),
        "tag": row["tag"] or "",
        "tagSource": row["tag_source"] or "",
        "thumbnail": row["thumbnail"] or "",
    }


def stored_tags(conn: sqlite3.Connection, file_id: str) -> dict[str, str]:
    return {face["id"]: face["tag"] for face in list_faces(conn, file_id) if face.get("tag")}


def metadata_needs_refresh(conn: sqlite3.Connection, photo_id: str) -> bool:
    row = conn.execute("select * from photo_metadata where photo_id = ?", (photo_id,)).fetchone()
    if not row:
        return True
    return not any(
        row[key] is not None
        for key in ("taken_at", "camera_make", "camera_model", "latitude", "longitude", "altitude", "orientation")
    ) and (row["exif_json"] or "{}") == "{}"


def save_file(conn: sqlite3.Connection, record: dict) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        insert into photos (id, path, name, type, signature, width, height, duration_seconds, indexed_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            path = excluded.path,
            name = excluded.name,
            type = excluded.type,
            signature = excluded.signature,
            width = excluded.width,
            height = excluded.height,
            duration_seconds = excluded.duration_seconds,
            indexed_at = excluded.indexed_at
        """,
        (
            record["id"],
            record["path"],
            record["name"],
            record["type"],
            record["signature"],
            record["width"],
            record["height"],
            record.get("durationSeconds"),
            now,
        ),
    )
    faces = filter_ignored_faces(conn, record["id"], record.get("faces", []))
    replace_faces(conn, record["id"], faces, source="manual", clusters=record.get("clusters", []))
    save_metadata(conn, record["id"], record.get("metadata", {}))
    save_place(conn, record["id"], record.get("place", {}))


def replace_faces(
    conn: sqlite3.Connection,
    photo_id: str,
    faces: list[dict],
    source: str,
    clusters: list[dict] | None = None,
) -> None:
    # Callers own the transaction so delete/insert replacement stays atomic per photo.
    reconciled_faces = reconcile_faces(conn, photo_id, faces)
    conn.execute(
        "delete from face_people where face_id in (select id from faces where photo_id = ?)",
        (photo_id,),
    )
    conn.execute("delete from faces where photo_id = ?", (photo_id,))
    conn.execute("delete from face_clusters where photo_id = ?", (photo_id,))

    for face in reconciled_faces:
        box = face["box"]
        conn.execute(
            """
            insert into faces
            (
                id, photo_id, box_x, box_y, box_width, box_height,
                cluster_id, frame_index, timestamp_seconds, det_score,
                embedding, thumbnail
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                face["id"],
                photo_id,
                box["x"],
                box["y"],
                box["width"],
                box["height"],
                face.get("clusterId"),
                face.get("frameIndex"),
                face.get("timestampSeconds"),
                face.get("detScore"),
                json.dumps(face.get("embedding", [])),
                face.get("thumbnail", ""),
            ),
        )

    for face in reconciled_faces:
        if face.get("tag"):
            set_face_tag(conn, face["id"], face["tag"], source=face.get("tagSource") or source)

    for cluster in clusters or []:
        conn.execute(
            """
            insert into face_clusters
            (
                id, photo_id, centroid, representative_face_id,
                representative_timestamp_seconds, face_count,
                first_seen_seconds, last_seen_seconds
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cluster["id"],
                photo_id,
                json.dumps(cluster.get("centroid", [])),
                cluster.get("representativeFaceId"),
                cluster.get("representativeTimestampSeconds"),
                cluster.get("faceCount", 0),
                cluster.get("firstSeenSeconds"),
                cluster.get("lastSeenSeconds"),
            ),
        )


def filter_ignored_faces(conn: sqlite3.Connection, photo_id: str, faces: list[dict]) -> list[dict]:
    ignored = ignored_faces(conn, photo_id)
    return [face for face in faces if not matches_ignored_face(face, ignored)]


def ignored_faces(conn: sqlite3.Connection, photo_id: str) -> list[dict]:
    rows = conn.execute("select * from ignored_faces where photo_id = ?", (photo_id,)).fetchall()
    return [
        {
            "box": {
                "x": row["box_x"],
                "y": row["box_y"],
                "width": row["box_width"],
                "height": row["box_height"],
            },
            "embedding": json.loads(row["embedding"] or "[]"),
        }
        for row in rows
    ]


def matches_ignored_face(face: dict, ignored: list[dict]) -> bool:
    for ignored_face in ignored:
        if embedding_similarity(face.get("embedding", []), ignored_face.get("embedding", [])) >= match_threshold():
            return True
        if box_iou(face.get("box", {}), ignored_face.get("box", {})) >= face_box_iou_threshold():
            return True
    return False


def box_iou(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    ax2 = a["x"] + a["width"]
    ay2 = a["y"] + a["height"]
    bx2 = b["x"] + b["width"]
    by2 = b["y"] + b["height"]
    intersection_width = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    intersection_height = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    intersection = intersection_width * intersection_height
    area_a = a["width"] * a["height"]
    area_b = b["width"] * b["height"]
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def ignore_face(conn: sqlite3.Connection, file_id: str, face_id: str) -> bool:
    row = conn.execute("select * from faces where photo_id = ? and id = ?", (file_id, face_id)).fetchone()
    if not row:
        return False
    face_ids = related_cluster_face_ids(conn, face_id)
    rows = conn.execute(
        f"select * from faces where id in ({', '.join('?' for _ in face_ids)})",
        tuple(face_ids),
    ).fetchall()
    tag_row = conn.execute(
        """
        select p.name
        from face_people fp
        join people p on p.id = fp.person_id
        where fp.face_id = ?
        """,
        (face_id,),
    ).fetchone()

    now = datetime.now(UTC).isoformat(timespec="seconds")
    ignored_rows = rows
    if row["cluster_id"]:
        cluster_row = conn.execute("select * from face_clusters where id = ?", (row["cluster_id"],)).fetchone()
        if cluster_row:
            representative = next(
                (current for current in rows if current["id"] == cluster_row["representative_face_id"]),
                rows[0],
            )
            ignored_rows = [
                {
                    **dict(representative),
                    "embedding": cluster_row["centroid"] or representative["embedding"],
                }
            ]

    conn.executemany(
        """
        insert into ignored_faces
        (photo_id, box_x, box_y, box_width, box_height, embedding, ignored_tag, created_at)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                file_id,
                current["box_x"],
                current["box_y"],
                current["box_width"],
                current["box_height"],
                current["embedding"],
                tag_row["name"] if tag_row else None,
                now,
            )
            for current in ignored_rows
        ],
    )
    placeholders = ", ".join("?" for _ in face_ids)
    conn.execute(f"delete from face_people where face_id in ({placeholders})", tuple(face_ids))
    conn.execute(f"delete from faces where id in ({placeholders})", tuple(face_ids))
    if row["cluster_id"]:
        conn.execute("delete from face_clusters where id = ?", (row["cluster_id"],))
    return True


def clear_ignored_faces(conn: sqlite3.Connection, file_id: str) -> None:
    conn.execute("delete from ignored_faces where photo_id = ?", (file_id,))


def reconcile_faces(conn: sqlite3.Connection, photo_id: str, new_faces: list[dict]) -> list[dict]:
    old_faces = list_faces(conn, photo_id)
    matched_old_ids = set()
    reconciled = []

    for face in new_faces:
        match = best_face_match(face, old_faces, matched_old_ids)
        if match:
            matched_old_ids.add(match["id"])
            face["id"] = match["id"]
            if match.get("tag") and match.get("tagSource") == "manual":
                face["tag"] = match["tag"]
                face["tagSource"] = "manual"
        else:
            face["id"] = f"face-{uuid4().hex}"
        reconciled.append(face)

    return reconciled


def best_face_match(face: dict, candidates: list[dict], used_ids: set[str]) -> dict | None:
    embedding = face.get("embedding", [])
    if not embedding:
        return None

    best = None
    best_score = 0.0
    for candidate in candidates:
        if candidate["id"] in used_ids:
            continue
        score = embedding_similarity(embedding, candidate.get("embedding", []))
        if score > best_score:
            best = candidate
            best_score = score

    return best if best_score >= face_reconcile_threshold() else None


def embedding_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def save_metadata(conn: sqlite3.Connection, photo_id: str, metadata: dict) -> None:
    conn.execute(
        """
        insert into photo_metadata
        (photo_id, taken_at, camera_make, camera_model, latitude, longitude, altitude, orientation, exif_json)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(photo_id) do update set
            taken_at = excluded.taken_at,
            camera_make = excluded.camera_make,
            camera_model = excluded.camera_model,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            altitude = excluded.altitude,
            orientation = excluded.orientation,
            exif_json = excluded.exif_json
        """,
        (
            photo_id,
            metadata.get("taken_at"),
            metadata.get("camera_make"),
            metadata.get("camera_model"),
            metadata.get("latitude"),
            metadata.get("longitude"),
            metadata.get("altitude"),
            metadata.get("orientation"),
            metadata.get("exif_json") or "{}",
        ),
    )


def save_place(conn: sqlite3.Connection, photo_id: str, place: dict) -> None:
    latitude = place.get("latitude")
    longitude = place.get("longitude")
    if latitude is None and longitude is None and not any(place.get(key) for key in ("city", "region", "country")):
        return

    conn.execute(
        """
        insert into photo_places
        (photo_id, city, region, country, latitude, longitude, source)
        values (?, ?, ?, ?, ?, ?, ?)
        on conflict(photo_id) do update set
            city = excluded.city,
            region = excluded.region,
            country = excluded.country,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            source = excluded.source
        """,
        (
            photo_id,
            place.get("city"),
            place.get("region"),
            place.get("country"),
            latitude,
            longitude,
            place.get("source"),
        ),
    )


def set_face_tag(conn: sqlite3.Connection, face_id: str, tag: str, source: str) -> None:
    face_ids = related_cluster_face_ids(conn, face_id)
    placeholders = ", ".join("?" for _ in face_ids)
    conn.execute(f"delete from face_people where face_id in ({placeholders})", tuple(face_ids))
    clean_tag = tag.strip()
    if not clean_tag:
        return
    person_id = get_or_create_person(conn, clean_tag)
    conn.executemany(
        """
        insert or replace into face_people (face_id, person_id, confidence, source)
        values (?, ?, ?, ?)
        """,
        [(current_face_id, person_id, None, source) for current_face_id in face_ids],
    )


def related_cluster_face_ids(conn: sqlite3.Connection, face_id: str) -> list[str]:
    row = conn.execute("select cluster_id from faces where id = ?", (face_id,)).fetchone()
    if not row or not row["cluster_id"]:
        return [face_id]
    rows = conn.execute("select id from faces where cluster_id = ?", (row["cluster_id"],)).fetchall()
    return [row["id"] for row in rows] or [face_id]


def get_or_create_person(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("select id from people where lower(name) = lower(?)", (name,)).fetchone()
    if row:
        return int(row["id"])

    cursor = conn.execute(
        "insert into people (name, created_at) values (?, ?)",
        (name, datetime.now(UTC).isoformat(timespec="seconds")),
    )
    return int(cursor.lastrowid)


def face_embedding(conn: sqlite3.Connection, face_id: str) -> list[float]:
    row = conn.execute("select embedding from faces where id = ?", (face_id,)).fetchone()
    if not row:
        return []
    return json.loads(row["embedding"] or "[]")


def untagged_faces(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select f.*
        from faces f
        left join face_people fp on fp.face_id = f.id
        where fp.face_id is null
        """
    ).fetchall()


def tagged_face_embeddings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        select
            f.embedding,
            p.name as tag
        from faces f
        join face_people fp on fp.face_id = f.id
        join people p on p.id = fp.person_id
        where f.embedding is not null
          and f.embedding != ''
        """
    ).fetchall()
    return [{"embedding": json.loads(row["embedding"] or "[]"), "tag": row["tag"]} for row in rows]


def update_faces(conn: sqlite3.Connection, file_id: str, faces: list[dict]) -> None:
    replace_faces(conn, file_id, faces, source="manual")


def clear_files(conn: sqlite3.Connection) -> None:
    # Delete order matters while foreign keys are enabled.
    # Keep schema/user_version intact; this clears indexed content, not the database structure.
    conn.execute("delete from face_people")
    conn.execute("delete from ignored_faces")
    conn.execute("delete from people")
    conn.execute("delete from face_clusters")
    conn.execute("delete from faces")
    conn.execute("delete from album_photos")
    conn.execute("delete from photo_tag_links")
    conn.execute("delete from albums")
    conn.execute("delete from photo_tags")
    conn.execute("delete from photo_places")
    conn.execute("delete from photo_metadata")
    conn.execute("delete from photos")
    if table_exists(conn, "files"):
        conn.execute("delete from files")


def row_dict(row: sqlite3.Row | None) -> dict:
    if not row:
        return {}
    return {key: row[key] for key in row.keys()}
