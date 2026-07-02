import unittest

from _helpers import assert_contains


class TestR15MergedPoseHint(unittest.TestCase):
    def test_stuck_prompt_reveals_temporary_camera_hint(self):
        assert_contains(
            self,
            "src/program_server/app/web/templates/game.html",
            "cam-hint-overlay",
            "cam-hint-cams",
            "서로의 모습을 잠깐 보여드릴게요",
        )
        assert_contains(
            self,
            "src/program_server/app/services/game_manager.py",
            "PROMPT_HINT_SECONDS = 10.0",
            "PEEK_DURATION_SECONDS = 2.5",
            "state.hint_cam_shown = True",
            "state.peek_until = now + PEEK_DURATION_SECONDS",
            '"show_hint_cams": show_hint_cams',
        )
        assert_contains(
            self,
            "src/program_server/app/web/static/js/game.js",
            "function renderCamHint",
            "state.show_hint_cams",
            "cam-hint-cam",
            "startCamHintSnapshots",
            "stopCamHintSnapshots",
        )


if __name__ == "__main__":
    unittest.main()
