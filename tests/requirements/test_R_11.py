import unittest

from _helpers import assert_contains


class TestR11RoundTiming(unittest.TestCase):
    def test_countdown_playing_result_timing_constants_and_transitions_exist(self):
        assert_contains(
            self,
            "server/app/services/game_manager.py",
            "COUNTDOWN_SECONDS = 3.0",
            "PLAY_SECONDS = 10.0",
            "RESULT_SECONDS = 4.0",
            "PHASE_COUNTDOWN",
            "PHASE_PLAYING",
            "PHASE_RESULT",
            "_enter_playing",
            "_finish_round",
            "_advance_round",
        )


if __name__ == "__main__":
    unittest.main()
