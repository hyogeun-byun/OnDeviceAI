import unittest

from _helpers import assert_contains, write_requirement_log


class TestR01MultiCameraWebSocket(unittest.TestCase):
    def test_camera_workers_connect_independently_by_id(self):
        assert_contains(
            self,
            "server/app/api/camera_routes.py",
            '@router.websocket("/{camera_id}/ws")',
            "stream_manager.update_frame(camera_id=camera_id",
            'message_type == "pose"',
        )
        assert_contains(
            self,
            "server/app/main.py",
            "StreamManager(camera_ids=config.camera_ids)",
            "camera_ids=config.camera_ids",
        )
        write_requirement_log(
            "R-01",
            "multi-camera-websocket",
            "unit_status=static_code_verified",
            "field_evidence_required=true",
            "field_reason=requires_two_or_more_camera_workers_and_one-worker-stop scenario",
            "expected_runtime_logs=test-results/requirements/R-01-multi-camera-websocket-server.log, test-results/requirements/R-01-multi-camera-websocket-camera-<CAMERA_NO>.log",
            "expected_metric_logs=test-results/requirements/R-01-multi-camera-websocket-camera-<CAMERA_NO>-metrics.jsonl",
            "sample_existing_logs=log/camera-worker-camera_02.log, log/camera-worker-camera_03.log",
        )


if __name__ == "__main__":
    unittest.main()
