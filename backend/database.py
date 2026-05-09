from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime
from uuid import uuid4

from .config import DB_PATH, match_threshold

SCHEMA_VERSION = 1


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
            indexed_at text not null
        );

        create table if not exists faces (
            id text primary key,
            photo_id text not null references photos(id) on delete cascade,
            box_x real not null,
            box_y real not null,
            box_width real not null,
            box_height real not null,
            embedding text,
            thumbnail text
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

        create index if not exists idx_photos_signature on photos(signature);
        create index if not exists idx_faces_photo_id on faces(photo_id);
        create index if not exists idx_photo_metadata_taken_at on photo_metadata(taken_at);
        create index if not exists idx_photo_metadata_lat_lon on photo_metadata(latitude, longitude);
        create index if not exists idx_photo_places_city on photo_places(city);
        create index if not exists idx_face_people_person_id on face_people(person_id);
        """
    )


def run_migrations(conn: sqlite3.Connection) -> None:
    version = conn.execute("pragma user_version").fetchone()[0]
    if version < 1:
        migrate_legacy_files(conn)
        conn.execute(f"pragma user_version = {SCHEMA_VERSION}")
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
def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            "select 1 from sqlite_master where type = 'table' and name = ?",
            (table_name,),
        ).fetchone()
    )


def list_files(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("select * from photos order by name").fetchall()
    return [photo_to_record(conn, row) for row in rows]


def search_files(conn: sqlite3.Connection, year: str | None = None, city: str | None = None) -> list[dict]:
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
        "faces": list_faces(conn, photo_row["id"]),
        "metadata": row_dict(metadata) if metadata else {},
        "place": row_dict(place) if place else {},
    }


def list_faces(conn: sqlite3.Connection, photo_id: str) -> list[dict]:
    rows = conn.execute(
        """
        select
            f.*,
            p.name as tag
        from faces f
        left join face_people fp on fp.face_id = f.id
        left join people p on p.id = fp.person_id
        where f.photo_id = ?
        order by f.id
        """,
        (photo_id,),
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
        "embedding": json.loads(row["embedding"] or "[]"),
        "tag": row["tag"] or "",
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
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn.execute(
        """
        insert into photos (id, path, name, type, signature, width, height, indexed_at)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            path = excluded.path,
            name = excluded.name,
            type = excluded.type,
            signature = excluded.signature,
            width = excluded.width,
            height = excluded.height,
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
            now,
        ),
    )
    replace_faces(conn, record["id"], record.get("faces", []), source="manual")
    save_metadata(conn, record["id"], record.get("metadata", {}))
    save_place(conn, record["id"], record.get("place", {}))


def replace_faces(conn: sqlite3.Connection, photo_id: str, faces: list[dict], source: str) -> None:
    reconciled_faces = reconcile_faces(conn, photo_id, faces)
    conn.execute(
        "delete from face_people where face_id in (select id from faces where photo_id = ?)",
        (photo_id,),
    )
    conn.execute("delete from faces where photo_id = ?", (photo_id,))

    for face in reconciled_faces:
        box = face["box"]
        conn.execute(
            """
            insert into faces
            (id, photo_id, box_x, box_y, box_width, box_height, embedding, thumbnail)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                face["id"],
                photo_id,
                box["x"],
                box["y"],
                box["width"],
                box["height"],
                json.dumps(face.get("embedding", [])),
                face.get("thumbnail", ""),
            ),
        )
        if face.get("tag"):
            set_face_tag(conn, face["id"], face["tag"], source=source)


def reconcile_faces(conn: sqlite3.Connection, photo_id: str, new_faces: list[dict]) -> list[dict]:
    old_faces = list_faces(conn, photo_id)
    matched_old_ids = set()
    reconciled = []

    for face in new_faces:
        match = best_face_match(face, old_faces, matched_old_ids)
        if match:
            matched_old_ids.add(match["id"])
            face["id"] = match["id"]
            if not face.get("tag") and match.get("tag"):
                face["tag"] = match["tag"]
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

    return best if best_score >= match_threshold() else None


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
    conn.execute("delete from face_people where face_id = ?", (face_id,))
    clean_tag = tag.strip()
    if not clean_tag:
        return
    person_id = get_or_create_person(conn, clean_tag)
    conn.execute(
        """
        insert or replace into face_people (face_id, person_id, confidence, source)
        values (?, ?, ?, ?)
        """,
        (face_id, person_id, None, source),
    )


def get_or_create_person(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("select id from people where lower(name) = lower(?)", (name,)).fetchone()
    if row:
        return int(row["id"])

    cursor = conn.execute(
        "insert into people (name, created_at) values (?, ?)",
        (name, datetime.utcnow().isoformat(timespec="seconds")),
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
    conn.execute("delete from face_people")
    conn.execute("delete from people")
    conn.execute("delete from faces")
    conn.execute("delete from photo_places")
    conn.execute("delete from photo_metadata")
    conn.execute("delete from photos")
    if table_exists(conn, "files"):
        conn.execute("delete from files")


def row_dict(row: sqlite3.Row | None) -> dict:
    if not row:
        return {}
    return {key: row[key] for key in row.keys()}
