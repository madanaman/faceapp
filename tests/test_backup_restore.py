from __future__ import annotations

import sqlite3
import tempfile
import unittest
import json
from pathlib import Path

from backend import database
from backend.backup import create_backup, restore_backup, validate_restore_source


class BackupRestoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media_dir = self.root / "media-source"
        self.media_dir.mkdir()
        self.media_file = self.media_dir / "birthday.jpg"
        self.media_file.write_bytes(b"fake image bytes")
        self.db_path = self.root / "face_index.sqlite3"
        self.thumbnail_dir = self.root / ".thumbnails"
        self.thumbnail_dir.mkdir()
        (self.thumbnail_dir / "face.jpg").write_bytes(b"thumbnail bytes")
        self.create_sample_database()

    def tearDown(self):
        self.temp.cleanup()

    def create_sample_database(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        database.ensure_schema(conn)
        database.run_migrations(conn)
        database.save_file(
            conn,
            {
                "id": str(self.media_file),
                "path": str(self.media_file),
                "name": self.media_file.name,
                "type": "image/jpeg",
                "signature": "birthday.jpg:16:1",
                "width": 100,
                "height": 100,
                "faces": [
                    {
                        "id": "candidate-1",
                        "box": {"x": 10, "y": 10, "width": 30, "height": 30},
                        "embedding": [1.0, 0.0],
                        "thumbnail": "",
                    }
                ],
                "metadata": {"taken_at": "2022-12-01T10:00:00"},
                "place": {"city": "Toronto", "region": "Ontario", "country": "Canada"},
            },
        )
        face_id = database.photo_to_record(conn, database.find_file(conn, str(self.media_file)))["faces"][0]["id"]
        database.set_face_tag(conn, face_id, "Aman", source="manual")
        album = database.create_album(conn, "Birthday")
        database.add_photo_to_album(conn, album["id"], str(self.media_file))
        database.add_photo_tag(conn, str(self.media_file), "first birthday")
        conn.commit()
        conn.close()

    def test_metadata_backup_creates_manifest_database_and_thumbnails(self):
        backup_root = self.root / "metadata-backup"

        result = create_backup(backup_root, include_media=False, db_path=self.db_path, thumbnail_dir=self.thumbnail_dir)
        manifest = result["manifest"]

        self.assertEqual(manifest["mode"], "metadata")
        self.assertEqual(manifest["counts"]["photos"], 1)
        self.assertEqual(manifest["counts"]["faces"], 1)
        self.assertEqual(manifest["thumbnails"]["count"], 1)
        self.assertTrue((backup_root / "manifest.json").exists())
        self.assertTrue((backup_root / "face_index.sqlite3").exists())
        self.assertTrue((backup_root / "thumbnails" / "face.jpg").exists())
        self.assertEqual(validate_restore_source(backup_root)["valid"], True)

    def test_full_backup_copies_media_and_records_checksum_mapping(self):
        backup_root = self.root / "full-backup"

        result = create_backup(backup_root, include_media=True, db_path=self.db_path, thumbnail_dir=self.thumbnail_dir)
        manifest = result["manifest"]

        self.assertEqual(manifest["mode"], "full")
        self.assertEqual(manifest["counts"]["mediaCopied"], 1)
        self.assertEqual(manifest["counts"]["mediaMissing"], 0)
        self.assertNotIn("media", manifest)
        self.assertEqual(manifest["mediaIndex"]["path"], "media-index.jsonl")
        self.assertEqual(manifest["mediaIndex"]["count"], 1)
        media_entry = json.loads((backup_root / "media-index.jsonl").read_text(encoding="utf-8").strip())
        self.assertEqual(media_entry["photoId"], str(self.media_file))
        self.assertEqual(media_entry["originalPath"], str(self.media_file))
        self.assertIn("media/by-id/", media_entry["backupPath"])
        self.assertTrue(media_entry["sha256"])
        self.assertTrue((backup_root / media_entry["backupPath"]).exists())
        self.assertEqual(validate_restore_source(backup_root)["valid"], True)

    def test_restore_validation_fails_for_missing_manifest(self):
        validation = validate_restore_source(self.root / "missing-backup")

        self.assertEqual(validation["valid"], False)
        self.assertIn("Backup manifest is missing.", validation["errors"])

    def test_restore_validation_fails_for_missing_media_index(self):
        backup_root = self.root / "full-backup-missing-index"
        backup = create_backup(backup_root, include_media=True, db_path=self.db_path, thumbnail_dir=self.thumbnail_dir)
        (backup_root / backup["manifest"]["mediaIndex"]["path"]).unlink()

        validation = validate_restore_source(backup_root)

        self.assertEqual(validation["valid"], False)
        self.assertIn("Backup media index file is missing.", validation["errors"])

    def test_metadata_restore_restores_database_and_thumbnails(self):
        backup_root = self.root / "metadata-backup"
        create_backup(backup_root, include_media=False, db_path=self.db_path, thumbnail_dir=self.thumbnail_dir)
        target_app_data = self.root / "metadata-restore-app"
        target_db = target_app_data / "face_index.sqlite3"
        target_thumbnails = target_app_data / ".thumbnails"

        result = restore_backup(
            backup_root,
            db_path=target_db,
            thumbnail_dir=target_thumbnails,
            app_data_dir=target_app_data,
        )

        self.assertEqual(result["mode"], "metadata")
        self.assertEqual(result["files"][0]["path"], str(self.media_file))
        self.assertEqual(result["files"][0]["faces"][0]["tag"], "Aman")
        self.assertEqual(result["files"][0]["albums"][0]["name"], "Birthday")
        self.assertEqual(result["files"][0]["tags"][0]["name"], "first birthday")
        self.assertEqual(result["files"][0]["place"]["city"], "Toronto")
        self.assertTrue((target_thumbnails / "face.jpg").exists())

    def test_full_restore_rewrites_photo_paths_to_restored_media(self):
        backup_root = self.root / "full-backup"
        create_backup(backup_root, include_media=True, db_path=self.db_path, thumbnail_dir=self.thumbnail_dir)
        target_app_data = self.root / "full-restore-app"
        target_db = target_app_data / "face_index.sqlite3"
        target_thumbnails = target_app_data / ".thumbnails"
        target_restored_media = target_app_data / "restored-media"

        result = restore_backup(
            backup_root,
            db_path=target_db,
            thumbnail_dir=target_thumbnails,
            restored_media_dir=target_restored_media,
            app_data_dir=target_app_data,
        )

        restored_path = Path(result["files"][0]["path"])
        self.assertEqual(result["mode"], "full")
        self.assertEqual(result["restoredMediaCount"], 1)
        self.assertTrue(restored_path.exists())
        self.assertIn("restored-media", restored_path.parts)
        self.assertEqual(restored_path.read_bytes(), self.media_file.read_bytes())
        self.assertEqual(result["files"][0]["faces"][0]["tag"], "Aman")

    def test_full_restore_allows_missing_backed_up_media_with_warning(self):
        backup_root = self.root / "partial-full-backup"
        backup = create_backup(backup_root, include_media=True, db_path=self.db_path, thumbnail_dir=self.thumbnail_dir)
        media_entry = json.loads((backup_root / backup["manifest"]["mediaIndex"]["path"]).read_text(encoding="utf-8").strip())
        (backup_root / media_entry["backupPath"]).unlink()
        target_app_data = self.root / "partial-restore-app"
        target_db = target_app_data / "face_index.sqlite3"
        target_thumbnails = target_app_data / ".thumbnails"
        target_restored_media = target_app_data / "restored-media"

        validation = validate_restore_source(backup_root)
        result = restore_backup(
            backup_root,
            db_path=target_db,
            thumbnail_dir=target_thumbnails,
            restored_media_dir=target_restored_media,
            app_data_dir=target_app_data,
        )

        self.assertTrue(validation["valid"])
        self.assertIn("Backed-up media file is missing", validation["warnings"][0])
        self.assertEqual(result["restoredMediaCount"], 0)
        self.assertEqual(result["skippedMediaCount"], 1)
        self.assertIn("Backed-up media file is missing", result["validation"]["warnings"][0])
        self.assertEqual(result["files"][0]["faces"][0]["tag"], "Aman")


if __name__ == "__main__":
    unittest.main()
