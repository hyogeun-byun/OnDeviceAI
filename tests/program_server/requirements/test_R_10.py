import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _helpers import assert_contains, load_path_module


class ConnectionProxy:
    def __init__(self, connection, close_calls):
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_close_calls", close_calls)

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __setattr__(self, name, value):
        setattr(self._connection, name, value)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, *exc_info):
        return self._connection.__exit__(*exc_info)

    def close(self):
        self._close_calls.append(self._connection)
        return self._connection.close()


class TestR10Leaderboard(unittest.TestCase):
    def test_sqlite_leaderboard_persists_and_orders_scores(self):
        leaderboard_mod = load_path_module("leaderboard_for_test", "src/program_server/app/services/leaderboard.py")
        with tempfile.TemporaryDirectory() as tmp:
            board = leaderboard_mod.Leaderboard(Path(tmp) / "scores.sqlite")
            board.add("Alpha", 50, "mid", "상황", [50, 50, 50, 50, 50])
            board.add("Bravo", 80, "high", "운동", [80, 80, 80, 80, 80])
            top = board.top()
        self.assertEqual(["Bravo", "Alpha"], [row["team_name"] for row in top])
        self.assertEqual([1, 2], [row["rank"] for row in top])

    def test_sqlite_connections_close_after_each_operation(self):
        leaderboard_mod = load_path_module("leaderboard_close_for_test", "src/program_server/app/services/leaderboard.py")
        original_connect = sqlite3.connect
        close_calls = []

        def connect_and_track(*args, **kwargs):
            return ConnectionProxy(original_connect(*args, **kwargs), close_calls)

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "scores.sqlite"
            with mock.patch.object(leaderboard_mod.sqlite3, "connect", side_effect=connect_and_track):
                board = leaderboard_mod.Leaderboard(db_path)
                board.add("Alpha", 50, "mid", "상황", [50])
                board.add("Bravo", 80, "high", "운동", [80])
                self.assertEqual(2, board.count())
                self.assertEqual("Bravo", board.top()[0]["team_name"])
                self.assertEqual(2, board.clear())

            self.assertGreaterEqual(len(close_calls), 6)
            db_path.unlink()

    def test_frontend_renders_leaderboard(self):
        assert_contains(
            self,
            "src/program_server/app/web/static/js/game.js",
            "refreshLeaderboardIdle",
            "refreshLeaderboardFinal",
            "leaderboard-list",
        )


if __name__ == "__main__":
    unittest.main()
