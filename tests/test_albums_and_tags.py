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

    def test_face_tag_is_visible_when_photo_record_is_reloaded(self):
        database.save_file(
            self.conn,
            {
                "id": "photo-1",
                "path": "/photos/birthday.jpg",
                "name": "birthday.jpg",
                "type": "image/jpeg",
                "signature": "sig-2",
                "width": 100,
                "height": 100,
                "faces": [
                    {
                        "id": "face-1",
                        "box": {"x": 10, "y": 10, "width": 40, "height": 40},
                        "embedding": [1.0, 0.0],
                        "thumbnail": "",
                    }
                ],
                "metadata": {},
                "place": {},
            },
        )

        record = database.photo_to_record(self.conn, database.find_file(self.conn, "photo-1"))
        database.set_face_tag(self.conn, record["faces"][0]["id"], "Aman", source="manual")
        record = database.photo_to_record(self.conn, database.find_file(self.conn, "photo-1"))

        self.assertEqual(record["faces"][0]["tag"], "Aman")
        self.assertEqual(record["faces"][0]["tagSource"], "manual")

    def test_album_and_tag_filters_are_case_insensitive(self):
        album = database.create_album(self.conn, "Malaysia Trip")
        database.add_photo_to_album(self.conn, album["id"], "photo-1")
        database.add_photo_tag(self.conn, "photo-1", "Aman's first birthday")

        self.assertEqual(len(database.search_files(self.conn, album="malaysia trip")), 1)
        self.assertEqual(len(database.search_files(self.conn, tag="aman's first birthday")), 1)

    def test_location_filters_match_city_region_or_country(self):
        database.save_place(
            self.conn,
            "photo-1",
            {"city": "Toronto", "region": "Ontario", "country": "Canada", "latitude": 43.65, "longitude": -79.38},
        )

        record = database.photo_to_record(self.conn, database.find_file(self.conn, "photo-1"))

        self.assertEqual(record["place"]["city"], "Toronto")
        self.assertEqual([place["name"] for place in database.list_places(self.conn)], ["Canada", "Ontario", "Toronto"])
        self.assertEqual(len(database.search_files(self.conn, place="toronto")), 1)
        self.assertEqual(len(database.search_files(self.conn, place="ontario")), 1)
        self.assertEqual(len(database.search_files(self.conn, place="canada")), 1)
        self.assertEqual(len(database.search_files(self.conn, region="ontario")), 1)
        self.assertEqual(len(database.search_files(self.conn, country="canada")), 1)

    def test_clear_files_removes_locations_and_location_cache(self):
        database.save_place(
            self.conn,
            "photo-1",
            {"city": "Toronto", "region": "Ontario", "country": "Canada", "latitude": 43.65, "longitude": -79.38},
        )
        database.save_location_cache(
            self.conn,
            43.65,
            -79.38,
            {"city": "Toronto", "region": "Ontario", "country": "Canada"},
            "nominatim",
        )

        database.clear_files(self.conn)

        self.assertEqual(database.list_places(self.conn), [])
        self.assertEqual(database.cached_location(self.conn, 43.65, -79.38), {})

    def test_location_source_precedence_keeps_manual_edits(self):
        database.save_place(self.conn, "photo-1", {"city": "Kuala Lumpur", "country": "Malaysia", "source": "manual"})
        database.save_place(
            self.conn,
            "photo-1",
            {"city": "Toronto", "region": "Ontario", "country": "Canada", "latitude": 43.65, "longitude": -79.38, "source": "gps_reverse_geocode"},
        )

        record = database.photo_to_record(self.conn, database.find_file(self.conn, "photo-1"))

        self.assertEqual(record["place"]["city"], "Kuala Lumpur")
        self.assertEqual(record["place"]["country"], "Malaysia")
        self.assertEqual(record["place"]["latitude"], 43.65)
        self.assertEqual(record["place"]["source"], "manual")

    def test_scan_default_can_be_replaced_by_gps_reverse_geocode(self):
        database.save_place(self.conn, "photo-1", {"city": "Malaysia Trip", "country": "Malaysia", "source": "scan_default"})
        database.save_place(
            self.conn,
            "photo-1",
            {"city": "Toronto", "region": "Ontario", "country": "Canada", "source": "gps_reverse_geocode"},
        )

        record = database.photo_to_record(self.conn, database.find_file(self.conn, "photo-1"))

        self.assertEqual(record["place"]["city"], "Toronto")
        self.assertEqual(record["place"]["source"], "gps_reverse_geocode")

    def test_location_resolver_candidates_include_scan_defaults_not_manual(self):
        database.save_place(
            self.conn,
            "photo-1",
            {"city": "Malaysia Trip", "country": "Malaysia", "latitude": 3.139, "longitude": 101.6869, "source": "scan_default"},
        )

        self.assertEqual(len(database.unresolved_gps_places(self.conn, 10)), 1)

        database.save_place(self.conn, "photo-1", {"city": "Kuala Lumpur", "country": "Malaysia", "source": "manual"})

        self.assertEqual(database.unresolved_gps_places(self.conn, 10), [])

    def test_location_cache_uses_rounded_coordinate_key(self):
        database.save_location_cache(
            self.conn,
            43.653226,
            -79.383184,
            {"city": "Toronto", "region": "Ontario", "country": "Canada"},
            "nominatim",
        )

        cached = database.cached_location(self.conn, 43.6532, -79.3831)

        self.assertEqual(cached["city"], "Toronto")
        self.assertEqual(cached["cache_key"], "43.653,-79.383")

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
