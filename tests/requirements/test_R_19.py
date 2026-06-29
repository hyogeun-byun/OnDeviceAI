import unittest

from _helpers import assert_contains, function_body, read


class TestR19NoLlmInPlayingPath(unittest.TestCase):
    def test_playing_gauge_update_does_not_call_llm_generation(self):
        manager = read("server/app/services/game_manager.py")
        body = function_body(manager, "_update_gauge")
        self.assertIn("analyze_group", body)
        self.assertIn("narrator.coach", body)
        self.assertNotIn("generate_prompts", body)
        self.assertNotIn("generate_mc_comment", body)
        self.assertNotIn("generate_final_report", body)
        self.assertNotIn("self._llm", body)
        assert_contains(
            self,
            "server/app/services/game_manager.py",
            "# Background LLM task helpers (never awaited from tick/playing)",
        )


if __name__ == "__main__":
    unittest.main()
