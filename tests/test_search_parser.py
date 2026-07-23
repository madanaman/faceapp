from __future__ import annotations

from datetime import date
import sqlite3
import unittest

from backend import database
from backend.search_parser import parse_search_query


class SearchParserTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma foreign_keys = on")
        database.ensure_schema(self.conn)
        database.run_migrations(self.conn)
        database.get_or_create_person(self.conn, "Aman")
        database.get_or_create_person(self.conn, "Preeti")
        database.create_album(self.conn, "Ironman Malaysia")
        database.create_photo_tag(self.conn, "first birthday")
        database.save_file(
            self.conn,
            {
                "id": "toronto-photo",
                "path": "/photos/toronto.jpg",
                "name": "toronto.jpg",
                "type": "image/jpeg",
                "signature": "sig-toronto",
                "width": 100,
                "height": 100,
                "faces": [],
                "metadata": {},
                "place": {"city": "Toronto", "region": "Ontario", "country": "Canada"},
            },
        )

    def tearDown(self):
        self.conn.close()

    def test_parses_people_album_tag_media_and_year(self):
        result = parse_search_query(
            self.conn,
            "show me Aman's first birthday photos from Ironman Malaysia in 2022",
            today=date(2026, 7, 19),
        )

        self.assertTrue(result["hasInterpretation"])
        self.assertEqual(result["terms"], ["Aman", "first birthday", "Ironman Malaysia"])
        self.assertEqual(result["mediaType"], "photos")
        self.assertEqual(result["year"], "2022")
        self.assertEqual(result["month"], "")
        self.assertEqual(result["date"], "")

    def test_parses_multiple_people_month_year_and_video(self):
        result = parse_search_query(
            self.conn,
            "show videos with Aman and Preeti from December 2022",
            today=date(2026, 7, 19),
        )

        self.assertEqual(result["terms"], ["Aman", "Preeti"])
        self.assertEqual(result["mediaType"], "videos")
        self.assertEqual(result["year"], "2022")
        self.assertEqual(result["month"], "12")

    def test_date_or_media_alone_is_still_a_valid_interpretation(self):
        result = parse_search_query(self.conn, "photos from 2022", today=date(2026, 7, 19))

        self.assertTrue(result["hasInterpretation"])
        self.assertEqual(result["terms"], [])
        self.assertEqual(result["mediaType"], "photos")
        self.assertEqual(result["year"], "2022")

    def test_unknown_words_do_not_become_search_terms(self):
        result = parse_search_query(self.conn, "random words I never tagged", today=date(2026, 7, 19))

        self.assertFalse(result["hasInterpretation"])
        self.assertEqual(result["terms"], [])
        self.assertIn("random", result["unusedWords"])

    def test_parses_known_location_names(self):
        result = parse_search_query(
            self.conn,
            "show me photos of Aman in Toronto from 2022",
            today=date(2026, 7, 19),
        )

        self.assertTrue(result["hasInterpretation"])
        self.assertEqual(result["terms"], ["Aman", "Toronto"])
        self.assertIn({"type": "place", "name": "Toronto"}, result["entities"])
        self.assertEqual(result["mediaType"], "photos")
        self.assertEqual(result["year"], "2022")


if __name__ == "__main__":
    unittest.main()
