import sqlite3
import unittest

from backend import database


class AlbumsAndTagsTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma foreign_keys = on")
        database.ensure_schema(self.conn)
        database.run_migrations(self.conn)
        self.save_photo()

    def tearDown(self):
        self.conn.close()

    def save_photo(self):
        database.save_file(
            self.conn,
            {
                "id": "photo-1",
                "path": "/photos/birthday.jpg",
                "name": "birthday.jpg",
                "type": "image/jpeg",
                "signature": "sig-1",
                "width": 100,
                "height": 100,
                "faces": [],
                "metadata": {},
                "place": {},
            },
        )

    def test_photo_can_belong_to_album_and_have_story_tag(self):
        album = database.create_album(self.conn, "Malaysia Trip")
        database.add_photo_to_album(self.conn, album["id"], "photo-1")
        database.add_photo_tag(self.conn, "photo-1", "Aman's first birthday")

        record = database.photo_to_record(self.conn, database.find_file(self.conn, "photo-1"))

        self.assertEqual(record["albums"], [{"id": album["id"], "name": "Malaysia Trip"}])
        self.assertEqual(record["tags"][0]["name"], "Aman's first birthday")
        self.assertEqual(database.list_albums(self.conn)[0]["photoCount"], 1)
        self.assertEqual(database.list_tags(self.conn)[0]["photoCount"], 1)

    def test_album_and_tag_filters_are_case_insensitive(self):
        album = database.create_album(self.conn, "Malaysia Trip")
        database.add_photo_to_album(self.conn, album["id"], "photo-1")
        database.add_photo_tag(self.conn, "photo-1", "Aman's first birthday")

        self.assertEqual(len(database.search_files(self.conn, album="malaysia trip")), 1)
        self.assertEqual(len(database.search_files(self.conn, tag="aman's first birthday")), 1)

    def test_rescan_preserves_album_membership_and_photo_tags(self):
        album = database.create_album(self.conn, "Malaysia Trip")
        database.add_photo_to_album(self.conn, album["id"], "photo-1")
        database.add_photo_tag(self.conn, "photo-1", "Aman's first birthday")

        self.save_photo()

        record = database.photo_to_record(self.conn, database.find_file(self.conn, "photo-1"))
        self.assertEqual(record["albums"][0]["name"], "Malaysia Trip")
        self.assertEqual(record["tags"][0]["name"], "Aman's first birthday")


if __name__ == "__main__":
    unittest.main()
