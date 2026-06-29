import unittest

from _helpers import load_path_module


class TestR13ActivityGate(unittest.TestCase):
    def test_activity_gate_penalizes_neutral_stillness(self):
        pose = load_path_module("pose_similarity_activity_for_test", "server/app/services/pose_similarity.py")
        self.assertAlmostEqual(pose.ACTIVITY_FLOOR, pose._activity_factor(0.0))
        self.assertAlmostEqual(1.0, pose._activity_factor(1.0))
        self.assertLess(pose._activity_factor(0.0), pose._activity_factor(0.6))


if __name__ == "__main__":
    unittest.main()
