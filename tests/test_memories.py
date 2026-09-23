from datetime import date
import sqlite3
import unittest

from backend import database
from backend.memories import generate_local_memories


class MemoriesTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma foreign_keys = on")
        database.ensure_schema(self.conn)
        database.run_migrations(self.conn)

    def tearDown(self):
        self.conn.close()

    def save_photo(self, photo_id, taken_at, name=None, faces=None, place=None):
        database.save_file(
            self.conn,
            {
                "id": photo_id,
                "path": f"/photos/{name or photo_id}.jpg",
                "name": name or f"{photo_id}.jpg",
                "type": "image/jpeg",
                "signature": f"sig-{photo_id}",
                "width": 100,
                "height": 100,
                "faces": faces or [],
                "metadata": {"taken_at": taken_at},
                "place": place or {},
            },
        )

    def save_tagged_photo(self, photo_id, taken_at, person):
        self.save_photo(
            photo_id,
            taken_at,
            faces=[
                {
                    "id": f"candidate-{photo_id}",
                    "box": {"x": 10, "y": 10, "width": 40, "height": 40},
                    "embedding": [1.0, 0.0],
                    "thumbnail": "",
                }
            ],
        )
        record = database.photo_to_record(self.conn, database.find_file(self.conn, photo_id))
        database.set_face_tag(self.conn, record["faces"][0]["id"], person, source="manual")

    def test_generates_on_this_day_memory_from_indexed_dates(self):
        self.save_photo("photo-2024", "2024-08-25T09:00:00")
        self.save_photo("photo-2025", "2025-08-25T10:00:00")

        memories = generate_local_memories(self.conn, today=date(2026, 8, 25))

        memory = next(memory for memory in memories if memory["type"] == "on_this_day")
        self.assertEqual(memory["id"], "on-this-day-08-25")
        self.assertEqual(memory["photoCount"], 2)
        self.assertEqual(set(memory["photoIds"]), {"photo-2024", "photo-2025"})

    def test_dismissed_memory_stays_hidden_after_regeneration(self):
        self.save_photo("photo-2024", "2024-08-25T09:00:00")
        self.save_photo("photo-2025", "2025-08-25T10:00:00")
        generate_local_memories(self.conn, today=date(2026, 8, 25))

        database.dismiss_memory(self.conn, "on-this-day-08-25")
        generate_local_memories(self.conn, today=date(2026, 8, 25))

        self.assertEqual(database.list_memories(self.conn), [])
        dismissed = database.list_memories(self.conn, include_dismissed=True)
        self.assertEqual(dismissed[0]["id"], "on-this-day-08-25")
        self.assertTrue(dismissed[0]["dismissedAt"])

    def test_generates_person_over_years_memory_from_face_tags(self):
        self.save_tagged_photo("aman-2022", "2022-05-01T09:00:00", "Aman")
        self.save_tagged_photo("aman-2025", "2025-05-01T09:00:00", "Aman")

        memories = generate_local_memories(self.conn, today=date(2026, 8, 25))

        memory = next(memory for memory in memories if memory["type"] == "people_over_time")
        self.assertEqual(memory["title"], "Aman over the years")
        self.assertEqual(set(memory["photoIds"]), {"aman-2022", "aman-2025"})

    def test_generates_album_tag_and_place_memories(self):
        self.save_photo("photo-1", "2024-01-01T09:00:00", place={"city": "Kuala Lumpur", "country": "Malaysia"})
        self.save_photo("photo-2", "2024-01-02T09:00:00", place={"city": "Kuala Lumpur", "country": "Malaysia"})
        album = database.create_album(self.conn, "Malaysia Trip")
        for photo_id in ("photo-1", "photo-2"):
            database.add_photo_to_album(self.conn, album["id"], photo_id)
            database.add_photo_tag(self.conn, photo_id, "Post Ironman")

        memories = generate_local_memories(self.conn, today=date(2026, 8, 25))
        types = {memory["type"] for memory in memories}

        self.assertIn("album", types)
        self.assertIn("photo_tag", types)
        self.assertIn("place", types)

    def test_clear_files_removes_generated_memories(self):
        self.save_photo("photo-2024", "2024-08-25T09:00:00")
        self.save_photo("photo-2025", "2025-08-25T10:00:00")
        generate_local_memories(self.conn, today=date(2026, 8, 25))

        database.clear_files(self.conn)

        self.assertEqual(database.list_memories(self.conn, include_dismissed=True), [])


if __name__ == "__main__":
    unittest.main()
