import unittest

from _helpers import assert_contains


class TestR05DashboardStatusMetrics(unittest.TestCase):
    def test_dashboard_exposes_status_keypoints_and_metrics(self):
        assert_contains(
            self,
            "server/app/web/templates/index.html",
            "server-status",
            "pose-state",
            "keypoint-count",
            "frame-fps",
            "pose-fps",
            "upload-kb-s",
        )
        assert_contains(
            self,
            "server/app/web/static/js/dashboard.js",
            'fetch("/api/cameras"',
            "camera.person_detected",
            "camera.keypoint_count",
            "workerMetrics.pose_fps",
            "workerMetrics.upload_kb_s",
        )


if __name__ == "__main__":
    unittest.main()
