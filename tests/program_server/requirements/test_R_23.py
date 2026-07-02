import unittest

from _helpers import assert_contains


class TestR23ResetAnyPhase(unittest.TestCase):
    def test_reset_route_and_buttons_return_to_idle_state(self):
        assert_contains(self, "src/program_server/app/api/game_routes.py", '@router.post("/reset")', "game_manager.reset()")
        assert_contains(self, "src/program_server/app/services/game_manager.py", "def reset", "GameState(theme=self._default_theme)")
        assert_contains(
            self,
            "src/program_server/app/web/static/js/game.js",
            "async function resetGame",
            'fetch("/api/game/reset"',
            "restart-game-btn",
            "restartBtn",
        )


if __name__ == "__main__":
    unittest.main()
