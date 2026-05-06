from __future__ import annotations

import json
import sqlite3

from .config import DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        create table if not exists files (
            id text primary key,
            name text not null,
            path text not null,
            type text not null,
            signature text not null,
            width real not null,
            height real not null,
            faces text not null
        )
        """
    )
    return conn


def row_to_record(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "path": row["path"],
        "type": row["type"],
        "signature": row["signature"],
        "width": row["width"],
        "height": row["height"],
        "faces": json.loads(row["faces"]),
    }


def list_files(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("select * from files order by name").fetchall()
    return [row_to_record(row) for row in rows]


def find_file(conn: sqlite3.Connection, file_id: str) -> sqlite3.Row | None:
    return conn.execute("select * from files where id = ?", (file_id,)).fetchone()


def find_current_file(conn: sqlite3.Connection, file_id: str, signature: str) -> sqlite3.Row | None:
    return conn.execute(
        "select * from files where id = ? and signature = ?",
        (file_id, signature),
    ).fetchone()


def stored_tags(conn: sqlite3.Connection, file_id: str) -> dict[str, str]:
    row = find_file(conn, file_id)
    if not row:
        return {}
    faces = json.loads(row["faces"])
    return {face["id"]: face.get("tag", "") for face in faces}


def save_file(conn: sqlite3.Connection, record: dict) -> None:
    conn.execute(
        """
        insert or replace into files
        (id, name, path, type, signature, width, height, faces)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["id"],
            record["name"],
            record["path"],
            record["type"],
            record["signature"],
            record["width"],
            record["height"],
            json.dumps(record["faces"]),
        ),
    )


def update_faces(conn: sqlite3.Connection, file_id: str, faces: list[dict]) -> None:
    conn.execute("update files set faces = ? where id = ?", (json.dumps(faces), file_id))


def clear_files(conn: sqlite3.Connection) -> None:
    conn.execute("delete from files")
