import unittest

from _helpers import assert_contains


class TestR24FinalScoreBreakdown(unittest.TestCase):
    def test_final_average_score_and_round_breakdown_are_rendered(self):
        assert_contains(
            self,
            "server/app/services/game_manager.py",
            "round_scores",
            "def _average_score",
            "return round(sum(scores) / len(scores), 1)",
            "final_title",
        )
        assert_contains(
            self,
            "server/app/web/static/js/game.js",
            "finalScore",
            "finalBreakdown",
            "state.round_scores",
            "state.total_score",
        )


if __name__ == "__main__":
    unittest.main()
