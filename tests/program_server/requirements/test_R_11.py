import unittest

from _helpers import assert_contains


class TestR11RoundTiming(unittest.TestCase):
    def test_sprint_state_machine_timing_constants_and_transitions_exist(self):
        assert_contains(
            self,
            "src/program_server/app/services/game_manager.py",
            "COUNTDOWN_SECONDS = 3.0",
            "GAME_TOTAL_SECONDS = 60.0",
            "REVEAL_SECONDS = 2.6",
            "PROMPT_HINT_SECONDS = 10.0",
            "PROMPT_MAX_SECONDS = 20.0",
            "CLEAR_FLASH_SECONDS = 3.0",
            "GIVEUP_FLASH_SECONDS = 1.6",
            "PHASE_CATEGORY",
            "PHASE_CAMTEST",
            "PHASE_COUNTDOWN",
            "PHASE_REVEAL",
            "PHASE_PLAYING",
            "PHASE_RESULT",
            "PHASE_GIVEUP",
            "PHASE_TIMEUP",
            "PHASE_FINISHED",
            "state.phase == PHASE_CAMTEST",
            "elif state.phase == PHASE_REVEAL",
            "elif state.phase == PHASE_PLAYING",
            "elif state.phase == PHASE_TIMEUP",
            "_enter_playing",
            "_finish_round",
            "_enter_giveup",
            "_enter_timeup",
            "_advance_round",
        )


if __name__ == "__main__":
    unittest.main()
