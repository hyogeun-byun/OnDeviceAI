import unittest

from _helpers import assert_contains


class TestR17GameWebSocketBroadcast(unittest.TestCase):
    def test_game_state_is_broadcast_at_10hz(self):
        assert_contains(
            self,
            "server/app/main.py",
            "GAME_TICK_HZ = 10.0",
            "await game_manager.tick()",
            "await game_hub.broadcast(game_manager.snapshot())",
        )
        assert_contains(self, "server/app/api/game_routes.py", '@router.websocket("/ws")')


if __name__ == "__main__":
    unittest.main()
