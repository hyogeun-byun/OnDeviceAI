import unittest

from _helpers import assert_contains, write_requirement_log


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
        write_requirement_log(
            "R-17",
            "game-websocket-10hz-sync",
            "unit_status=server_broadcast_loop_verified",
            "field_evidence_required=true",
            "field_reason=requires_two_browser clients or recorded timing comparison between /game and /stage",
            "field_success_criteria=phase/gauge/timer match within 1 second",
            "expected_runtime_logs=test-results/requirements/R-17-game-websocket-10hz-sync-server.log",
            "expected_capture=screen recording or browser console log for /game and /stage",
        )


if __name__ == "__main__":
    unittest.main()
