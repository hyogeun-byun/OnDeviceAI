import unittest

from _helpers import assert_contains


class TestR03MediaPipePose(unittest.TestCase):
    def test_mediapipe_lite_33_landmarks_10fps_is_declared_and_used(self):
        assert_contains(
            self,
            "camera-worker/app/inference/pose_estimator.py",
            "MediaPipe Pose",
            "Outputs 33 landmarks",
            '_BACKEND = "mediapipe"',
            "model_complexity=model_complexity",
        )
        assert_contains(self, "camera-worker/app/constants.py", "KEYPOINT_INFERENCE_FPS = 10.0")
        assert_contains(self, "camera-worker/requirements.txt", "mediapipe==0.10.18")
        assert_contains(
            self,
            "SW_Bootcamp_13기_최종제출/SW_Bootcamp_13기_A반_3팀_요구사항_명세서.md",
            "MediaPipe Pose Lite",
            "33개",
            "9fps 이상",
        )


if __name__ == "__main__":
    unittest.main()
