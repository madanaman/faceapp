import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

if "PIL" not in sys.modules:
    pil = types.ModuleType("PIL")
    pil.ExifTags = types.SimpleNamespace(TAGS={}, GPSTAGS={}, IFD=types.SimpleNamespace(GPSInfo=0))
    pil.Image = types.SimpleNamespace(open=lambda path: None)
    sys.modules["PIL"] = pil

from backend import database, scanner


class ScanAlbumTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp_dir.name)
        self.photo = self.folder / "trip.jpg"
        self.photo.write_bytes(b"fake image bytes")
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma foreign_keys = on")
        database.ensure_schema(self.conn)
        database.run_migrations(self.conn)

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    @contextmanager
    def connection(self):
        yield self.conn

    def scan(self, album_name):
        analysis = {
            "width": 100,
            "height": 100,
            "durationSeconds": None,
            "faces": [],
            "warnings": [],
        }
        with (
            patch.object(scanner.database, "connection", self.connection),
            patch.object(scanner, "analyze_path", return_value=analysis),
            patch.object(scanner, "extract_photo_metadata", return_value={}),
        ):
            return scanner.scan_folder(self.folder, scan_mode="photos", album_name=album_name)

    def test_scan_assigns_new_and_existing_files_to_album(self):
        first = self.scan("Malaysia Trip")
        self.assertEqual(first["files"][0]["albums"][0]["name"], "Malaysia Trip")
        self.assertEqual(first["albums"][0]["photoCount"], 1)

        second = self.scan("Family Favorites")
        albums = {album["name"] for album in second["files"][0]["albums"]}

        self.assertEqual(albums, {"Malaysia Trip", "Family Favorites"})
        self.assertEqual(len(second["albums"]), 2)


if __name__ == "__main__":
    unittest.main()
