import unittest

from _helpers import load_path_module


class TestR12PoseSimilarity(unittest.TestCase):
    def test_score_uses_face_and_upper_body_six_bone_vectors(self):
        pose = load_path_module("pose_similarity_for_test", "server/app/services/pose_similarity.py")
        self.assertEqual(
            {
                "head_left",
                "head_right",
                "left_upper_arm",
                "left_forearm",
                "right_upper_arm",
                "right_forearm",
            },
            set(pose.BONE_DEFINITIONS),
        )
        self.assertEqual(6, len(pose.BONE_DEFINITIONS))
        self.assertAlmostEqual(
            100.0,
            pose.pose_pair_similarity({"left_forearm": (1.0, 0.0)}, {"left_forearm": (1.0, 0.0)}),
        )
        self.assertLess(
            pose.pose_pair_similarity({"left_forearm": (1.0, 0.0)}, {"left_forearm": (0.0, 1.0)}),
            100.0,
        )


if __name__ == "__main__":
    unittest.main()
