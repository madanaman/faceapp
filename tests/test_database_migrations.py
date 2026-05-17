import sqlite3
import unittest

from backend import database


class DatabaseMigrationTest(unittest.TestCase):
    def test_cluster_indexes_are_created_after_face_columns_exist(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            create table photos (
                id text primary key,
                path text not null,
                name text not null,
                type text not null,
                signature text not null,
                width real,
                height real,
                indexed_at text not null
            );
            create table faces (
                id text primary key,
                photo_id text not null,
                box_x real not null,
                box_y real not null,
                box_width real not null,
                box_height real not null,
                embedding text,
                thumbnail text
            );
            pragma user_version = 3;
            """
        )

        database.ensure_schema(conn)
        database.run_migrations(conn)

        columns = {row["name"] for row in conn.execute("pragma table_info(faces)").fetchall()}
        indexes = {row["name"] for row in conn.execute("pragma index_list(faces)").fetchall()}
        self.assertIn("cluster_id", columns)
        self.assertIn("idx_faces_cluster_id", indexes)

    def test_cluster_tag_is_returned_from_non_representative_face(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        database.ensure_schema(conn)
        database.run_migrations(conn)
        conn.execute(
            """
            insert into photos
            (id, path, name, type, signature, width, height, duration_seconds, indexed_at)
            values ('video-1', 'video-1.mp4', 'video-1.mp4', 'video/mp4', 'sig', 100, 100, 10, 'now')
            """
        )
        conn.executemany(
            """
            insert into faces
            (id, photo_id, box_x, box_y, box_width, box_height, cluster_id, embedding, thumbnail)
            values (?, 'video-1', 0, 0, 10, 10, 'cluster-1', '[]', '')
            """,
            [("face-representative",), ("face-tagged",)],
        )
        conn.execute(
            """
            insert into face_clusters
            (id, photo_id, representative_face_id, face_count)
            values ('cluster-1', 'video-1', 'face-representative', 2)
            """
        )
        person_id = database.get_or_create_person(conn, "Alex")
        conn.execute(
            """
            insert into face_people (face_id, person_id, confidence, source)
            values ('face-tagged', ?, null, 'manual')
            """,
            (person_id,),
        )

        faces = database.list_faces(conn, "video-1")

        self.assertEqual(len(faces), 1)
        self.assertEqual(faces[0]["id"], "face-representative")
        self.assertEqual(faces[0]["tag"], "Alex")
        self.assertEqual(faces[0]["tagSource"], "manual")

    def test_ignoring_cluster_stores_one_centroid_row(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        database.ensure_schema(conn)
        database.run_migrations(conn)
        conn.execute(
            """
            insert into photos
            (id, path, name, type, signature, width, height, duration_seconds, indexed_at)
            values ('video-1', 'video-1.mp4', 'video-1.mp4', 'video/mp4', 'sig', 100, 100, 10, 'now')
            """
        )
        conn.executemany(
            """
            insert into faces
            (id, photo_id, box_x, box_y, box_width, box_height, cluster_id, embedding, thumbnail)
            values (?, 'video-1', ?, ?, 10, 10, 'cluster-1', ?, '')
            """,
            [
                ("face-representative", 0, 0, "[1.0, 0.0]"),
                ("face-member", 20, 20, "[0.9, 0.1]"),
            ],
        )
        conn.execute(
            """
            insert into face_clusters
            (id, photo_id, centroid, representative_face_id, face_count)
            values ('cluster-1', 'video-1', '[0.95, 0.05]', 'face-representative', 2)
            """
        )

        self.assertTrue(database.ignore_face(conn, "video-1", "face-member"))

        ignored = conn.execute("select * from ignored_faces where photo_id = 'video-1'").fetchall()
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]["embedding"], "[0.95, 0.05]")


if __name__ == "__main__":
    unittest.main()
