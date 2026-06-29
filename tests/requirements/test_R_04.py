import unittest

from _helpers import assert_contains


class TestR04ThreadSeparation(unittest.TestCase):
    def test_capture_frame_sending_and_pose_inference_have_separate_threads(self):
        assert_contains(
            self,
            "camera-worker/app/main.py",
            "def capture_loop",
            "def frame_sender_loop",
            "def pose_inference_loop",
            "Queue(maxsize=1)",
            'name="camera-capture"',
            'name="frame-sender"',
            'name="pose-inference"',
        )


if __name__ == "__main__":
    unittest.main()
