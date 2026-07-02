import unittest

from _helpers import assert_contains


class TestR07TeamAndTPoseStart(unittest.TestCase):
    def test_team_name_stage_api_and_tpose_progress_exist(self):
        assert_contains(self, "src/program_server/app/api/game_routes.py", '@router.post("/stage")', "game_manager.stage")
        assert_contains(
            self,
            "src/program_server/app/services/game_manager.py",
            "READY_POSE_HOLD_SECONDS = 1.5",
            "detect_ready_pose",
            "_check_idle_ready_pose",
            "_enter_category",
        )
        assert_contains(
            self,
            "src/program_server/app/web/templates/game.html",
            'id="team-name"',
            "tpose-progress-fill",
            "T자",
        )


if __name__ == "__main__":
    unittest.main()
