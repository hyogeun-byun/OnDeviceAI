import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _helpers import assert_contains, load_path_module, write_requirement_log


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
            "camera-worker/app/metrics.py",
            "frame_fps",
            "pose_fps",
            "_write_metrics_payload",
        )
        assert_contains(
            self,
            "SW_Bootcamp_13기_최종제출/SW_Bootcamp_13기_A반_3팀_요구사항_명세서.md",
            "MediaPipe Pose Lite",
            "33개",
            "9fps 이상",
        )

    def test_worker_metrics_writes_actual_fps_jsonl(self):
        metrics_module = load_path_module("camera_worker_metrics_for_test", "camera-worker/app/metrics.py")
        CameraWorkerMetrics = metrics_module.CameraWorkerMetrics

        with TemporaryDirectory() as tmpdir:
            metrics_log_path = Path(tmpdir) / "camera-worker-camera_01-metrics.jsonl"
            metrics = CameraWorkerMetrics(
                camera_id="camera_01",
                log_interval_seconds=0.01,
                metrics_log_path=metrics_log_path,
            )
            metrics.record_frame(frame_bytes=1024, capture_ms=1.0, encode_ms=1.0, frame_upload_ms=1.0)
            metrics.record_pose(pose_ms=1.0, pose_upload_ms=1.0)
            time.sleep(0.02)

            payload = metrics.maybe_collect()
            record = json.loads(metrics_log_path.read_text(encoding="utf-8").strip())

            self.assertIsNotNone(payload)
            self.assertEqual(record["camera_id"], "camera_01")
            self.assertGreater(record["frame_fps"], 0)
            self.assertGreater(record["pose_fps"], 0)
            self.assertIn("timestamp", record)
            write_requirement_log(
                "R-03",
                "pose-fps-33-landmarks",
                "unit_status=metrics_jsonl_writer_verified",
                "unit_generated_metrics_jsonl=true",
                "field_evidence_required=true",
                "field_success_criteria=pose_fps>=9 and keypoints=33 in dashboard/server pose payload",
                "expected_runtime_logs=test-results/requirements/R-03-pose-fps-33-landmarks-camera-<CAMERA_NO>.log",
                "expected_metric_logs=test-results/requirements/R-03-pose-fps-33-landmarks-camera-<CAMERA_NO>-metrics.jsonl",
                "sample_existing_logs=log/camera-worker-camera_02-metrics.jsonl, log/camera-worker-camera_03-metrics.jsonl",
            )


if __name__ == "__main__":
    unittest.main()
