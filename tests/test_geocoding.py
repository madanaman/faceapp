import unittest
import sqlite3
from unittest.mock import patch

from backend import database, geocoding


class GeocodingTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma foreign_keys = on")
        database.ensure_schema(self.conn)
        database.run_migrations(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_nominatim_response_maps_to_city_region_country(self):
        place = geocoding.parse_nominatim_place(
            {
                "address": {
                    "city": "Toronto",
                    "state": "Ontario",
                    "country": "Canada",
                }
            }
        )

        self.assertEqual(place, {"city": "Toronto", "region": "Ontario", "country": "Canada"})

    def test_nominatim_parser_falls_back_to_town_or_village(self):
        place = geocoding.parse_nominatim_place(
            {
                "address": {
                    "town": "Banff",
                    "province": "Alberta",
                    "country": "Canada",
                }
            }
        )

        self.assertEqual(place["city"], "Banff")
        self.assertEqual(place["region"], "Alberta")

    def test_location_suggestions_use_known_local_places(self):
        database.save_location_cache(
            self.conn,
            28.6139,
            77.209,
            {"city": "New Delhi", "region": "Delhi", "country": "India"},
            "nominatim",
        )

        with patch.object(geocoding, "location_reverse_geocoding_enabled", return_value=False):
            suggestions = geocoding.suggest_locations(self.conn, "delhi", limit=5)

        self.assertEqual(suggestions[0]["label"], "New Delhi, Delhi, India")
        self.assertEqual(suggestions[0]["provider"], "nominatim")

    def test_location_payload_can_resolve_one_field_label(self):
        database.save_location_cache(
            self.conn,
            28.6139,
            77.209,
            {"city": "New Delhi", "region": "Delhi", "country": "India"},
            "nominatim",
        )

        with patch.object(geocoding, "location_reverse_geocoding_enabled", return_value=False):
            location = geocoding.location_from_payload(self.conn, {"location": {"label": "Delhi"}})

        self.assertEqual(location["city"], "New Delhi")
        self.assertEqual(location["region"], "Delhi")
        self.assertEqual(location["country"], "India")
        self.assertEqual(location["latitude"], 28.6139)


if __name__ == "__main__":
    unittest.main()
