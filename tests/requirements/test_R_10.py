import tempfile
import unittest
from pathlib import Path

from _helpers import assert_contains, load_path_module


class TestR10Leaderboard(unittest.TestCase):
    def test_sqlite_leaderboard_persists_and_orders_scores(self):
        leaderboard_mod = load_path_module("leaderboard_for_test", "server/app/services/leaderboard.py")
        with tempfile.TemporaryDirectory() as tmp:
            board = leaderboard_mod.Leaderboard(Path(tmp) / "scores.sqlite")
            board.add("Alpha", 50, "mid", "상황", [50, 50, 50, 50, 50])
            board.add("Bravo", 80, "high", "운동", [80, 80, 80, 80, 80])
            top = board.top()
        self.assertEqual(["Bravo", "Alpha"], [row["team_name"] for row in top])
        self.assertEqual([1, 2], [row["rank"] for row in top])

    def test_frontend_renders_leaderboard(self):
        assert_contains(
            self,
            "server/app/web/static/js/game.js",
            "refreshLeaderboardIdle",
            "refreshLeaderboardFinal",
            "leaderboard-list",
        )


if __name__ == "__main__":
    unittest.main()
