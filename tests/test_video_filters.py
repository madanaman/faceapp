import unittest

from backend.video import is_main_video_face


class VideoFilterTest(unittest.TestCase):
    def test_rejects_low_confidence_faces(self):
        face = {"detScore": 0.5, "box": {"height": 80}}

        self.assertFalse(is_main_video_face(face, min_score=0.7, min_face_height=40))

    def test_rejects_small_background_faces(self):
        face = {"detScore": 0.95, "box": {"height": 20}}

        self.assertFalse(is_main_video_face(face, min_score=0.7, min_face_height=40))

    def test_accepts_confident_large_faces(self):
        face = {"detScore": 0.95, "box": {"height": 80}}

        self.assertTrue(is_main_video_face(face, min_score=0.7, min_face_height=40))


if __name__ == "__main__":
    unittest.main()
