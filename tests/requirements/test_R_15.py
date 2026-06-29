import unittest

from _helpers import assert_contains


class TestR15MergedPoseHint(unittest.TestCase):
    def test_low_gauge_merged_skeleton_hint_is_present(self):
        assert_contains(
            self,
            "server/app/web/templates/game.html",
            "merged-skel-canvas",
            "포즈 싱크 힌트",
        )
        assert_contains(
            self,
            "server/app/web/static/js/game.js",
            "function drawMergedSkeletons",
            "latestGauge <= 40",
            "40점 이하일 때 힌트 공개!",
            "fetch(`/api/cameras/${player.camera_id}/pose`",
        )


if __name__ == "__main__":
    unittest.main()
