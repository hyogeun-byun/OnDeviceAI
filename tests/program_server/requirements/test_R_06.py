import unittest

from _helpers import assert_contains


class TestR06DashboardPoseOverlay(unittest.TestCase):
    def test_dashboard_draws_keypoints_and_connections_on_canvas(self):
        assert_contains(self, "src/program_server/app/web/templates/index.html", 'class="pose-overlay"')
        assert_contains(
            self,
            "src/program_server/app/web/static/js/dashboard.js",
            "POSE_CONNECTIONS",
            "function drawSkeleton",
            "ctx.lineTo",
            "ctx.arc",
            "refreshSkeletons",
        )


if __name__ == "__main__":
    unittest.main()
