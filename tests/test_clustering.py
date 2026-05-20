import unittest

from backend.clustering import cluster_faces, merge_clusters_by_tag


def face(face_id, embedding):
    return {
        "id": face_id,
        "box": {"x": 0, "y": 0, "width": 10, "height": 10},
        "embedding": embedding,
        "detScore": 0.9,
        "timestampSeconds": 1.0,
    }


class VideoClusteringTest(unittest.TestCase):
    def test_similar_embeddings_cluster_together(self):
        clusters = cluster_faces(
            [
                face("a", [1.0, 0.0, 0.0]),
                face("b", [0.99, 0.1, 0.0]),
            ],
            threshold=0.9,
        )

        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["faceCount"], 2)
        self.assertEqual({item["clusterId"] for item in clusters[0]["faces"]}, {clusters[0]["id"]})

    def test_different_embeddings_stay_separate(self):
        clusters = cluster_faces(
            [
                face("a", [1.0, 0.0, 0.0]),
                face("b", [0.0, 1.0, 0.0]),
            ],
            threshold=0.9,
        )

        self.assertEqual(len(clusters), 2)

    def test_empty_video_has_no_clusters(self):
        self.assertEqual(cluster_faces([], threshold=0.9), [])

    def test_single_face_video_produces_one_cluster(self):
        clusters = cluster_faces([face("a", [1.0, 0.0, 0.0])], threshold=0.9)

        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["representativeFaceId"], "a")
        self.assertEqual(clusters[0]["firstSeenSeconds"], 1.0)

    def test_known_same_tag_clusters_merge(self):
        first = face("a", [1.0, 0.0, 0.0])
        first["tag"] = "Alex"
        second = face("b", [0.0, 1.0, 0.0])
        second["tag"] = "alex"
        clusters = [
            {"id": "cluster-a", "faces": [first], "centroid": first["embedding"]},
            {"id": "cluster-b", "faces": [second], "centroid": second["embedding"]},
        ]

        merged = merge_clusters_by_tag(clusters)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["faceCount"], 2)
        self.assertEqual({item["clusterId"] for item in merged[0]["faces"]}, {merged[0]["id"]})


if __name__ == "__main__":
    unittest.main()
