import unittest

from _helpers import assert_contains, write_requirement_log


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
        write_requirement_log(
            "R-04",
            "threaded-capture-frame-pose",
            "unit_status=thread_structure_verified",
            "field_evidence_required=true",
            "field_success_criteria=frame_fps stays near target while pose_fps is recorded and failed_frames does not accumulate",
            "expected_runtime_logs=test-results/requirements/R-04-threaded-capture-frame-pose-camera-<CAMERA_NO>.log",
            "expected_metric_logs=test-results/requirements/R-04-threaded-capture-frame-pose-camera-<CAMERA_NO>-metrics.jsonl",
            "sample_existing_logs=log/camera-worker-camera_02.log, log/camera-worker-camera_03.log",
        )


if __name__ == "__main__":
    unittest.main()
