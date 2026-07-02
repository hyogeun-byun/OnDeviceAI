import unittest

from _helpers import assert_contains


class TestR24FinalScoreBreakdown(unittest.TestCase):
    def test_final_clear_count_seconds_and_round_breakdown_are_rendered(self):
        assert_contains(
            self,
            "src/program_server/app/services/game_manager.py",
            "round_scores",
            "def _average_score",
            "return float(self._state.cleared_count)",
            "final_seconds",
            "cleared_count",
            "final_title",
        )
        assert_contains(
            self,
            "src/program_server/app/web/static/js/game.js",
            "finalScore",
            "finalSummary",
            "finalBreakdown",
            "state.cleared_count",
            "state.final_seconds",
            "state.round_scores",
            "state.total_score",
        )
        assert_contains(
            self,
            "src/program_server/app/services/leaderboard.py",
            "score DESC",
            "total_time ASC",
        )


if __name__ == "__main__":
    unittest.main()
